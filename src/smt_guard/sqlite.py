"""SQLite persistence and transactional lifecycle adapters for SMT Guard."""

import hashlib
import json
import sqlite3
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from smt_guard.audit import AuditEntry
from smt_guard.bom import BomDocument, BomStatus, BomVersion, Material, Product
from smt_guard.configuration import ConfigurationStatus, ProductConfigurationRecord
from smt_guard.master_data import (
    Device,
    DuplicateCodeError,
    MasterDataError,
    ReferencedEntityError,
    Station,
    UnknownEntityError,
    normalize_code,
)
from smt_guard.migrations import MIGRATIONS, Migration
from smt_guard.records import Attempt
from smt_guard.run import ProductionRun, RunStationState, RunStatus
from smt_guard.scan import ProductConfiguration
from smt_guard.verification import VerificationResult


class MigrationError(RuntimeError):
    """Raised when schema history is inconsistent or a migration fails."""


class DuplicateConfigurationError(ValueError):
    """Raised when a product configuration identity already exists."""


class UnknownConfigurationError(LookupError):
    """Raised when a product configuration cannot be found."""


class InvalidLifecycleTransition(ValueError):
    """Raised when a persisted entity cannot enter the requested state."""


class UnknownBomVersionError(LookupError):
    """Raised when a BOM version cannot be found."""


class UnknownRunError(LookupError):
    """Raised when a production run cannot be found."""


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime) -> str:
    return value.isoformat()


def _parse_datetime(value: object) -> datetime:
    text = str(value)
    return datetime.fromisoformat(text) if text else datetime.min.replace(tzinfo=UTC)


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _write_audit(
    connection: sqlite3.Connection,
    *,
    actor: str,
    action: str,
    entity_type: str,
    entity_key: str,
    before: object | None = None,
    after: object | None = None,
    timestamp: datetime | None = None,
) -> None:
    connection.execute(
        "INSERT INTO audit_logs "
        "(timestamp, actor, action, entity_type, entity_key, before_json, after_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            _iso(timestamp or _utc_now()),
            actor.strip() or "SYSTEM",
            action,
            entity_type,
            entity_key,
            None if before is None else _json(before),
            None if after is None else _json(after),
        ),
    )


class SqliteDatabase:
    """Apply ordered schema migrations and verify immutable migration history."""

    SCHEMA_VERSION = MIGRATIONS[-1].version

    def __init__(
        self,
        connection: sqlite3.Connection,
        migrations: tuple[Migration, ...] = MIGRATIONS,
    ) -> None:
        self._connection = connection
        self._migrations = migrations

    def initialize(self) -> None:
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                checksum TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
            """
        )
        self._connection.commit()

        user_version = int(self._connection.execute("PRAGMA user_version").fetchone()[0])
        if user_version > self.SCHEMA_VERSION:
            raise MigrationError(
                f"Database schema version {user_version} is newer than supported "
                f"version {self.SCHEMA_VERSION}"
            )

        applied = self._applied_migrations()
        if not applied and user_version == 1:
            self._baseline_legacy_v1()
            applied = self._applied_migrations()
        elif not applied and user_version != 0:
            raise MigrationError(f"Schema version {user_version} has no migration history")

        self._verify_history(applied)
        history_version = max(applied, default=0)
        if user_version < history_version:
            self._repair_lagging_user_version(history_version)
        elif user_version > history_version:
            raise MigrationError(
                f"PRAGMA user_version {user_version} does not match migration history "
                f"{history_version}"
            )
        current = max(applied, default=0)
        for migration in self._migrations:
            if migration.version > current:
                self._apply(migration)
                current = migration.version

    def _applied_migrations(self) -> dict[int, tuple[str, str]]:
        rows = self._connection.execute(
            "SELECT version, name, checksum FROM schema_migrations ORDER BY version"
        )
        return {int(row[0]): (str(row[1]), str(row[2])) for row in rows}

    def _baseline_legacy_v1(self) -> None:
        required = {
            "devices",
            "stations",
            "product_configurations",
            "station_assignments",
            "attempts",
        }
        tables = {
            str(row[0])
            for row in self._connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        if not required <= tables:
            raise MigrationError("Legacy schema version 1 is incomplete")
        migration = self._migrations[0]
        with self._connection:
            self._connection.execute(
                "INSERT INTO schema_migrations (version, name, checksum, applied_at) "
                "VALUES (?, ?, ?, ?)",
                (migration.version, migration.name, self._checksum(migration), _iso(_utc_now())),
            )

    def _verify_history(
        self,
        applied: dict[int, tuple[str, str]],
    ) -> None:
        expected_versions = list(range(1, max(applied, default=0) + 1))
        if list(applied) != expected_versions:
            raise MigrationError("Schema migration history is not contiguous")
        known = {migration.version: migration for migration in self._migrations}
        for version, (name, checksum) in applied.items():
            migration = known.get(version)
            if migration is None:
                raise MigrationError(f"Unknown applied schema migration: {version}")
            if (name, checksum) != (migration.name, self._checksum(migration)):
                raise MigrationError(f"Schema migration {version} was modified after application")

    def _repair_lagging_user_version(self, history_version: int) -> None:
        """Repair redundant metadata after validating the complete migration history."""
        safe_version = int(history_version)
        try:
            self._connection.execute(f"PRAGMA user_version = {safe_version}")
            self._connection.commit()
        except sqlite3.Error as error:
            if self._connection.in_transaction:
                self._connection.rollback()
            raise MigrationError(
                f"Failed to repair PRAGMA user_version to {safe_version}"
            ) from error
        repaired = int(self._connection.execute("PRAGMA user_version").fetchone()[0])
        if repaired != safe_version:
            raise MigrationError(f"Failed to repair PRAGMA user_version to {safe_version}")

    def _apply(self, migration: Migration) -> None:
        checksum = self._checksum(migration)
        applied_at = _iso(_utc_now())
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            for statement in self._sql_statements(migration.up_sql):
                self._connection.execute(statement)
            self._connection.execute(
                "INSERT INTO schema_migrations (version, name, checksum, applied_at) "
                "VALUES (?, ?, ?, ?)",
                (migration.version, migration.name, checksum, applied_at),
            )
            safe_version = int(migration.version)
            self._connection.execute(f"PRAGMA user_version = {safe_version}")
            self._connection.commit()
        except sqlite3.Error as error:
            if self._connection.in_transaction:
                self._connection.rollback()
            raise MigrationError(
                f"Failed to apply schema migration {migration.version}_{migration.name}"
            ) from error

    @staticmethod
    def _checksum(migration: Migration) -> str:
        return hashlib.sha256(migration.up_sql.encode("utf-8")).hexdigest()

    @staticmethod
    def _sql_statements(script: str) -> list[str]:
        """Split trusted migration SQL while preserving multi-statement triggers."""
        statements: list[str] = []
        buffer = ""
        for line in script.splitlines(keepends=True):
            buffer += line
            if sqlite3.complete_statement(buffer):
                statement = buffer.strip()
                if statement:
                    statements.append(statement)
                buffer = ""
        if buffer.strip():
            raise MigrationError("Migration contains an incomplete SQL statement")
        return statements


class SqliteMasterDataRepository:
    """Persist device/station lifecycle rules with audit events."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def add_device(self, code: str, name: str, line: str, *, actor: str = "SYSTEM") -> Device:
        now = _iso(_utc_now())
        device = Device(normalize_code(code), name.strip(), line.strip())
        try:
            with self._connection:
                self._connection.execute(
                    "INSERT INTO devices "
                    "(code, name, line, enabled, archived, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (device.code, device.name, device.line, 1, 0, now, now),
                )
                _write_audit(
                    self._connection,
                    actor=actor,
                    action="CREATE",
                    entity_type="DEVICE",
                    entity_key=device.code,
                    after=asdict(device),
                )
        except sqlite3.IntegrityError as error:
            raise DuplicateCodeError(f"Duplicate device code: {device.code}") from error
        return device

    def update_device(
        self,
        code: str,
        *,
        name: str,
        line: str,
        actor: str = "SYSTEM",
    ) -> Device:
        before = self.get_device(code)
        with self._connection:
            self._connection.execute(
                "UPDATE devices SET name = ?, line = ?, updated_at = ? WHERE code = ?",
                (name.strip(), line.strip(), _iso(_utc_now()), before.code),
            )
            after = replace(before, name=name.strip(), line=line.strip())
            _write_audit(
                self._connection,
                actor=actor,
                action="UPDATE",
                entity_type="DEVICE",
                entity_key=before.code,
                before=asdict(before),
                after=asdict(after),
            )
        return after

    def disable_device(self, code: str, *, actor: str = "SYSTEM") -> None:
        self._set_device_enabled(code, False, actor)

    def enable_device(self, code: str, *, actor: str = "SYSTEM") -> None:
        device = self.get_device(code)
        if device.archived:
            raise MasterDataError(f"Archived device cannot be enabled: {device.code}")
        self._set_device_enabled(code, True, actor)

    def _set_device_enabled(self, code: str, enabled: bool, actor: str) -> None:
        before = self.get_device(code)
        with self._connection:
            self._connection.execute(
                "UPDATE devices SET enabled = ?, updated_at = ? WHERE code = ?",
                (int(enabled), _iso(_utc_now()), before.code),
            )
            _write_audit(
                self._connection,
                actor=actor,
                action="ENABLE" if enabled else "DISABLE",
                entity_type="DEVICE",
                entity_key=before.code,
                before={"enabled": before.enabled},
                after={"enabled": enabled},
            )

    def archive_device(self, code: str, *, actor: str = "SYSTEM") -> None:
        device = self.get_device(code)
        with self._connection:
            self._connection.execute(
                "UPDATE devices SET enabled = 0, archived = 1, updated_at = ? WHERE code = ?",
                (_iso(_utc_now()), device.code),
            )
            self._connection.execute(
                "UPDATE stations SET enabled = 0, archived = 1, updated_at = ? "
                "WHERE device_code = ?",
                (_iso(_utc_now()), device.code),
            )
            _write_audit(
                self._connection,
                actor=actor,
                action="ARCHIVE",
                entity_type="DEVICE",
                entity_key=device.code,
                before=asdict(device),
                after={"enabled": False, "archived": True},
            )

    def delete_device(self, code: str, *, actor: str = "SYSTEM") -> None:
        device = self.get_device(code)
        station_count = int(
            self._connection.execute(
                "SELECT COUNT(*) FROM stations WHERE device_code = ?", (device.code,)
            ).fetchone()[0]
        )
        if station_count:
            raise ReferencedEntityError(f"Device with stations cannot be deleted: {device.code}")
        with self._connection:
            self._connection.execute("DELETE FROM devices WHERE code = ?", (device.code,))
            _write_audit(
                self._connection,
                actor=actor,
                action="DELETE",
                entity_type="DEVICE",
                entity_key=device.code,
                before=asdict(device),
            )

    def get_device(self, code: str) -> Device:
        normalized = normalize_code(code)
        row = self._connection.execute(
            "SELECT code, name, line, enabled, archived FROM devices WHERE code = ?",
            (normalized,),
        ).fetchone()
        if row is None:
            raise UnknownEntityError(f"Unknown device: {normalized}")
        return Device(str(row[0]), str(row[1]), str(row[2]), bool(row[3]), bool(row[4]))

    def list_devices(self) -> list[Device]:
        rows = self._connection.execute(
            "SELECT code, name, line, enabled, archived FROM devices ORDER BY code"
        )
        return [Device(str(r[0]), str(r[1]), str(r[2]), bool(r[3]), bool(r[4])) for r in rows]

    def search_devices(
        self,
        query: str = "",
        *,
        enabled: bool | None = None,
        include_archived: bool = False,
    ) -> list[Device]:
        """Filter device master data without changing identity fields."""
        pattern = f"%{query.strip()}%"
        rows = self._connection.execute(
            "SELECT code, name, line, enabled, archived FROM devices "
            "WHERE (? = '%%' OR code LIKE ? OR name LIKE ? OR line LIKE ?) "
            "AND (? IS NULL OR enabled = ?) "
            "AND (? = 1 OR archived = 0) ORDER BY code",
            (
                pattern,
                pattern,
                pattern,
                pattern,
                None if enabled is None else int(enabled),
                None if enabled is None else int(enabled),
                int(include_archived),
            ),
        )
        return [Device(str(r[0]), str(r[1]), str(r[2]), bool(r[3]), bool(r[4])) for r in rows]

    def is_device_enabled(self, code: str) -> bool:
        try:
            device = self.get_device(code)
            return device.enabled and not device.archived
        except UnknownEntityError:
            return False

    def add_station(
        self,
        device_code: str,
        station_code: str,
        *,
        name: str = "",
        actor: str = "SYSTEM",
    ) -> Station:
        device = self.get_device(device_code)
        station = Station(device.code, normalize_code(station_code), name=name.strip())
        try:
            with self._connection:
                self._insert_station(station)
                _write_audit(
                    self._connection,
                    actor=actor,
                    action="CREATE",
                    entity_type="STATION",
                    entity_key=f"{station.device_code}/{station.code}",
                    after=asdict(station),
                )
        except sqlite3.IntegrityError as error:
            raise DuplicateCodeError(
                f"Duplicate station code: {station.device_code}/{station.code}"
            ) from error
        return station

    def bulk_add_stations(
        self,
        device_code: str,
        prefix: str,
        start: int,
        end: int,
        *,
        width: int,
        actor: str = "SYSTEM",
    ) -> list[Station]:
        device = self.get_device(device_code)
        stations = [
            Station(device.code, f"{prefix}{number:0{width}d}")
            for number in range(start, end + 1)
        ]
        try:
            with self._connection:
                for station in stations:
                    self._insert_station(station)
                    _write_audit(
                        self._connection,
                        actor=actor,
                        action="CREATE",
                        entity_type="STATION",
                        entity_key=f"{station.device_code}/{station.code}",
                        after=asdict(station),
                    )
        except sqlite3.IntegrityError as error:
            duplicate = next(
                (
                    item.code
                    for item in stations
                    if self._station_exists(item.device_code, item.code)
                ),
                stations[0].code,
            )
            raise DuplicateCodeError(
                f"Duplicate station code: {device.code}/{duplicate}"
            ) from error
        return stations

    def get_station(self, device_code: str, station_code: str) -> Station:
        device = normalize_code(device_code)
        station = normalize_code(station_code)
        row = self._connection.execute(
            "SELECT device_code, code, enabled, referenced, name, archived "
            "FROM stations WHERE device_code = ? AND code = ?",
            (device, station),
        ).fetchone()
        if row is None:
            raise UnknownEntityError(f"Unknown station: {device}/{station}")
        return Station(
            str(row[0]), str(row[1]), bool(row[2]), bool(row[3]), str(row[4]), bool(row[5])
        )

    def list_stations(self, device_code: str) -> list[Station]:
        device = self.get_device(device_code)
        rows = self._connection.execute(
            "SELECT device_code, code, enabled, referenced, name, archived "
            "FROM stations WHERE device_code = ? ORDER BY code",
            (device.code,),
        )
        return [
            Station(str(r[0]), str(r[1]), bool(r[2]), bool(r[3]), str(r[4]), bool(r[5]))
            for r in rows
        ]

    def search_stations(
        self,
        device_code: str,
        query: str = "",
        *,
        enabled: bool | None = None,
        include_archived: bool = False,
    ) -> list[Station]:
        """Filter stations within a device for management screens."""
        device = self.get_device(device_code)
        pattern = f"%{query.strip()}%"
        rows = self._connection.execute(
            "SELECT device_code, code, enabled, referenced, name, archived FROM stations "
            "WHERE device_code = ? AND (? = '%%' OR code LIKE ? OR name LIKE ?) "
            "AND (? IS NULL OR enabled = ?) "
            "AND (? = 1 OR archived = 0) ORDER BY code",
            (
                device.code,
                pattern,
                pattern,
                pattern,
                None if enabled is None else int(enabled),
                None if enabled is None else int(enabled),
                int(include_archived),
            ),
        )
        return [
            Station(str(r[0]), str(r[1]), bool(r[2]), bool(r[3]), str(r[4]), bool(r[5]))
            for r in rows
        ]

    def update_station(
        self,
        device_code: str,
        station_code: str,
        *,
        name: str,
        actor: str = "SYSTEM",
    ) -> Station:
        before = self.get_station(device_code, station_code)
        after = replace(before, name=name.strip())
        with self._connection:
            self._connection.execute(
                "UPDATE stations SET name = ?, updated_at = ? "
                "WHERE device_code = ? AND code = ?",
                (after.name, _iso(_utc_now()), before.device_code, before.code),
            )
            _write_audit(
                self._connection,
                actor=actor,
                action="UPDATE",
                entity_type="STATION",
                entity_key=f"{before.device_code}/{before.code}",
                before=asdict(before),
                after=asdict(after),
            )
        return after

    def is_station_enabled(self, device_code: str, station_code: str) -> bool:
        try:
            station = self.get_station(device_code, station_code)
            return (
                station.enabled
                and not station.archived
                and self.is_device_enabled(station.device_code)
            )
        except UnknownEntityError:
            return False

    def disable_station(
        self, device_code: str, station_code: str, *, actor: str = "SYSTEM"
    ) -> None:
        self._set_station_enabled(device_code, station_code, False, actor)

    def enable_station(
        self, device_code: str, station_code: str, *, actor: str = "SYSTEM"
    ) -> None:
        station = self.get_station(device_code, station_code)
        if station.archived:
            raise MasterDataError(
                f"Archived station cannot be enabled: {station.device_code}/{station.code}"
            )
        self._set_station_enabled(device_code, station_code, True, actor)

    def _set_station_enabled(
        self, device_code: str, station_code: str, enabled: bool, actor: str
    ) -> None:
        station = self.get_station(device_code, station_code)
        with self._connection:
            self._connection.execute(
                "UPDATE stations SET enabled = ?, updated_at = ? "
                "WHERE device_code = ? AND code = ?",
                (int(enabled), _iso(_utc_now()), station.device_code, station.code),
            )
            _write_audit(
                self._connection,
                actor=actor,
                action="ENABLE" if enabled else "DISABLE",
                entity_type="STATION",
                entity_key=f"{station.device_code}/{station.code}",
                before={"enabled": station.enabled},
                after={"enabled": enabled},
            )

    def mark_station_referenced(self, device_code: str, station_code: str) -> None:
        station = self.get_station(device_code, station_code)
        with self._connection:
            self._connection.execute(
                "UPDATE stations SET referenced = 1 WHERE device_code = ? AND code = ?",
                (station.device_code, station.code),
            )

    def archive_station(
        self, device_code: str, station_code: str, *, actor: str = "SYSTEM"
    ) -> None:
        station = self.get_station(device_code, station_code)
        with self._connection:
            self._connection.execute(
                "UPDATE stations SET enabled = 0, archived = 1, updated_at = ? "
                "WHERE device_code = ? AND code = ?",
                (_iso(_utc_now()), station.device_code, station.code),
            )
            _write_audit(
                self._connection,
                actor=actor,
                action="ARCHIVE",
                entity_type="STATION",
                entity_key=f"{station.device_code}/{station.code}",
                before=asdict(station),
                after={"enabled": False, "archived": True},
            )

    def delete_station(
        self, device_code: str, station_code: str, *, actor: str = "SYSTEM"
    ) -> None:
        station = self.get_station(device_code, station_code)
        referenced = station.referenced or self._connection.execute(
            "SELECT 1 FROM station_assignments WHERE device_code = ? AND station_code = ? "
            "UNION ALL SELECT 1 FROM run_station_states "
            "WHERE device_code = ? AND station_code = ? LIMIT 1",
            (station.device_code, station.code, station.device_code, station.code),
        ).fetchone() is not None
        if referenced:
            raise ReferencedEntityError(
                f"Referenced station cannot be deleted: {station.device_code}/{station.code}"
            )
        with self._connection:
            self._connection.execute(
                "DELETE FROM stations WHERE device_code = ? AND code = ?",
                (station.device_code, station.code),
            )
            _write_audit(
                self._connection,
                actor=actor,
                action="DELETE",
                entity_type="STATION",
                entity_key=f"{station.device_code}/{station.code}",
                before=asdict(station),
            )

    def _insert_station(self, station: Station) -> None:
        now = _iso(_utc_now())
        self._connection.execute(
            "INSERT INTO stations "
            "(device_code, code, enabled, referenced, name, archived, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                station.device_code,
                station.code,
                int(station.enabled),
                int(station.referenced),
                station.name,
                int(station.archived),
                now,
                now,
            ),
        )

    def _station_exists(self, device_code: str, station_code: str) -> bool:
        return self._connection.execute(
            "SELECT 1 FROM stations WHERE device_code = ? AND code = ?",
            (device_code, station_code),
        ).fetchone() is not None


class SqliteBomRepository:
    """Persist immutable, versioned BOMs and their import provenance."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def import_document(
        self,
        document: BomDocument,
        source_path: Path,
        *,
        operator: str,
        imported_at: datetime,
        version: str | None = None,
    ) -> BomVersion:
        source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
        normalized_version = (version or document.product.bom_number or source_hash[:12]).strip()
        try:
            with self._connection:
                cursor = self._connection.execute(
                    "INSERT INTO bom_versions "
                    "(product_code, version, bom_number, bom_name, product_name, "
                    "product_specification, status, source_filename, source_sha256, "
                    "imported_at, imported_by) VALUES (?, ?, ?, ?, ?, ?, 'DRAFT', ?, ?, ?, ?)",
                    (
                        document.product.material_code,
                        normalized_version,
                        document.product.bom_number,
                        document.product.bom_name,
                        document.product.name,
                        document.product.specification,
                        source_path.name,
                        source_hash,
                        _iso(imported_at),
                        operator.strip() or "SYSTEM",
                    ),
                )
                if cursor.lastrowid is None:
                    raise RuntimeError("SQLite did not allocate a BOM version identifier")
                bom_id = cursor.lastrowid
                for material in document.materials.values():
                    self._connection.execute(
                        "INSERT INTO bom_items "
                        "(bom_version_id, material_code, name, specification, quantity, category) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            bom_id,
                            material.code,
                            material.name,
                            material.specification,
                            material.quantity,
                            material.category,
                        ),
                    )
                _write_audit(
                    self._connection,
                    actor=operator,
                    action="IMPORT",
                    entity_type="BOM",
                    entity_key=f"{document.product.material_code}/{normalized_version}",
                    after={
                        "source_filename": source_path.name,
                        "source_sha256": source_hash,
                        "material_count": len(document.materials),
                    },
                    timestamp=imported_at,
                )
        except sqlite3.IntegrityError as error:
            raise InvalidLifecycleTransition(
                f"BOM version already exists: {document.product.material_code}/{normalized_version}"
            ) from error
        return self.get_by_id(bom_id)

    def get(self, product_code: str, version: str) -> BomVersion:
        row = self._connection.execute(
            "SELECT id FROM bom_versions WHERE product_code = ? AND version = ?",
            (normalize_code(product_code), normalize_code(version)),
        ).fetchone()
        if row is None:
            raise UnknownBomVersionError(f"Unknown BOM version: {product_code}/{version}")
        return self.get_by_id(int(row[0]))

    def get_by_id(self, bom_id: int) -> BomVersion:
        row = self._connection.execute(
            "SELECT id, product_code, version, bom_number, bom_name, product_name, "
            "product_specification, status, source_filename, source_sha256, imported_at, "
            "imported_by, published_at, activated_at FROM bom_versions WHERE id = ?",
            (bom_id,),
        ).fetchone()
        if row is None:
            raise UnknownBomVersionError(f"Unknown BOM version identifier: {bom_id}")
        materials = {
            str(item[0]): Material(
                str(item[0]), str(item[1]), str(item[2]), str(item[3]), str(item[4])
            )
            for item in self._connection.execute(
                "SELECT material_code, name, specification, quantity, category "
                "FROM bom_items WHERE bom_version_id = ? ORDER BY material_code",
                (bom_id,),
            )
        }
        document = BomDocument(
            Product(str(row[1]), str(row[3]), str(row[4]), str(row[5]), str(row[6])),
            materials,
        )
        return BomVersion(
            id=int(row[0]),
            version=str(row[2]),
            document=document,
            status=BomStatus(str(row[7])),
            source_filename=str(row[8]),
            source_sha256=str(row[9]),
            imported_at=_parse_datetime(row[10]),
            imported_by=str(row[11]),
            published_at=None if row[12] is None else _parse_datetime(row[12]),
            activated_at=None if row[13] is None else _parse_datetime(row[13]),
        )

    def list_versions(self, product_code: str | None = None) -> list[BomVersion]:
        if product_code is None:
            rows = self._connection.execute(
                "SELECT id FROM bom_versions ORDER BY product_code, imported_at, id"
            )
        else:
            rows = self._connection.execute(
                "SELECT id FROM bom_versions WHERE product_code = ? ORDER BY imported_at, id",
                (normalize_code(product_code),),
            )
        return [self.get_by_id(int(row[0])) for row in rows]

    def publish(
        self, product_code: str, version: str, *, actor: str = "SYSTEM"
    ) -> BomVersion:
        return self._transition(product_code, version, BomStatus.DRAFT, BomStatus.PUBLISHED, actor)

    def activate(
        self, product_code: str, version: str, *, actor: str = "SYSTEM"
    ) -> BomVersion:
        current = self.get(product_code, version)
        if current.status not in {BomStatus.PUBLISHED, BomStatus.OBSOLETE}:
            raise InvalidLifecycleTransition(
                f"BOM must be published before activation: {product_code}/{version}"
            )
        with self._connection:
            replaced = self._connection.execute(
                "SELECT id, version FROM bom_versions "
                "WHERE product_code = ? AND status = 'ACTIVE' AND id <> ?",
                (current.document.product.material_code, current.id),
            ).fetchall()
            self._connection.execute(
                "UPDATE bom_versions SET status = 'PUBLISHED' "
                "WHERE product_code = ? AND status = 'ACTIVE'",
                (current.document.product.material_code,),
            )
            for _, replaced_version in replaced:
                _write_audit(
                    self._connection,
                    actor=actor,
                    action="PUBLISHED",
                    entity_type="BOM",
                    entity_key=f"{product_code}/{replaced_version}",
                    before={"status": BomStatus.ACTIVE.value},
                    after={"status": BomStatus.PUBLISHED.value},
                )
            self._connection.execute(
                "UPDATE bom_versions SET status = 'ACTIVE', activated_at = ? WHERE id = ?",
                (_iso(_utc_now()), current.id),
            )
            _write_audit(
                self._connection,
                actor=actor,
                action="ACTIVATE",
                entity_type="BOM",
                entity_key=f"{product_code}/{version}",
                before={"status": current.status.value},
                after={"status": BomStatus.ACTIVE.value},
            )
        return self.get_by_id(current.id)

    def obsolete(
        self, product_code: str, version: str, *, actor: str = "SYSTEM"
    ) -> BomVersion:
        current = self.get(product_code, version)
        if current.status not in {BomStatus.PUBLISHED, BomStatus.ACTIVE}:
            raise InvalidLifecycleTransition(f"BOM cannot be obsoleted from {current.status.value}")
        return self._transition_any(current, BomStatus.OBSOLETE, actor)

    def archive(
        self, product_code: str, version: str, *, actor: str = "SYSTEM"
    ) -> BomVersion:
        current = self.get(product_code, version)
        if current.status is BomStatus.ACTIVE:
            raise InvalidLifecycleTransition("Active BOM must be obsoleted before archival")
        return self._transition_any(current, BomStatus.ARCHIVED, actor)

    def compare(self, first_id: int, second_id: int) -> dict[str, object]:
        first = self.get_by_id(first_id).document.materials
        second = self.get_by_id(second_id).document.materials
        first_codes = set(first)
        second_codes = set(second)
        changed = sorted(
            code for code in first_codes & second_codes if first[code] != second[code]
        )
        return {
            "added": sorted(second_codes - first_codes),
            "removed": sorted(first_codes - second_codes),
            "changed": changed,
        }

    def _transition(
        self,
        product_code: str,
        version: str,
        expected: BomStatus,
        target: BomStatus,
        actor: str,
    ) -> BomVersion:
        current = self.get(product_code, version)
        if current.status is not expected:
            raise InvalidLifecycleTransition(
                f"BOM {product_code}/{version} is {current.status.value}, expected {expected.value}"
            )
        return self._transition_any(current, target, actor)

    def _transition_any(
        self, current: BomVersion, target: BomStatus, actor: str
    ) -> BomVersion:
        published_at = _iso(_utc_now()) if target is BomStatus.PUBLISHED else None
        with self._connection:
            self._connection.execute(
                "UPDATE bom_versions SET status = ?, "
                "published_at = COALESCE(?, published_at) WHERE id = ?",
                (target.value, published_at, current.id),
            )
            _write_audit(
                self._connection,
                actor=actor,
                action=target.value,
                entity_type="BOM",
                entity_key=(
                    f"{current.document.product.material_code}/{current.version}"
                ),
                before={"status": current.status.value},
                after={"status": target.value},
            )
        return self.get_by_id(current.id)


class SqliteProductConfigurationRepository:
    """Persist immutable station-configuration versions and lifecycle state."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def save(
        self,
        configuration: ProductConfiguration,
        *,
        actor: str = "SYSTEM",
        activate: bool = True,
    ) -> None:
        product_code = normalize_code(configuration.product_code)
        version = normalize_code(configuration.version)
        errors = self.validate(configuration)
        if errors:
            raise InvalidLifecycleTransition("; ".join(errors))
        now = _iso(_utc_now())
        try:
            with self._connection:
                self._connection.execute(
                    "INSERT INTO product_configurations "
                    "(product_code, version, status, bom_version_id, created_at, created_by) "
                    "VALUES (?, ?, 'DRAFT', ?, ?, ?)",
                    (
                        product_code,
                        version,
                        configuration.bom_version_id,
                        now,
                        actor.strip() or "SYSTEM",
                    ),
                )
                for (device_code, station_code), material_code in configuration.assignments.items():
                    device = normalize_code(device_code)
                    station = normalize_code(station_code)
                    self._connection.execute(
                        "INSERT INTO station_assignments "
                        "(product_code, version, device_code, station_code, material_code) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (product_code, version, device, station, normalize_code(material_code)),
                    )
                    self._connection.execute(
                        "UPDATE stations SET referenced = 1 WHERE device_code = ? AND code = ?",
                        (device, station),
                    )
                target = ConfigurationStatus.ACTIVE if activate else ConfigurationStatus.DRAFT
                if activate:
                    self._connection.execute(
                        "UPDATE product_configurations SET status = 'ACTIVE', "
                        "published_at = ?, activated_at = ? "
                        "WHERE product_code = ? AND version = ?",
                        (now, now, product_code, version),
                    )
                _write_audit(
                    self._connection,
                    actor=actor,
                    action="CREATE",
                    entity_type="PRODUCT_CONFIGURATION",
                    entity_key=f"{product_code}/{version}",
                    after={"status": target.value, "assignments": len(configuration.assignments)},
                )
        except sqlite3.IntegrityError as error:
            if self._exists(product_code, version):
                raise DuplicateConfigurationError(
                    f"Duplicate product configuration: {product_code}/{version}"
                ) from error
            raise

    def create_draft(
        self, configuration: ProductConfiguration, *, actor: str = "SYSTEM"
    ) -> None:
        self.save(configuration, actor=actor, activate=False)

    def update_draft(
        self, configuration: ProductConfiguration, *, actor: str = "SYSTEM"
    ) -> ProductConfigurationRecord:
        """Atomically replace the assignments of an editable draft."""
        current = self.get_record(configuration.product_code, configuration.version)
        if current.status is not ConfigurationStatus.DRAFT:
            raise InvalidLifecycleTransition("Only draft configurations can be edited")
        errors = self.validate(configuration)
        if errors:
            raise InvalidLifecycleTransition("; ".join(errors))
        product = normalize_code(configuration.product_code)
        version = normalize_code(configuration.version)
        with self._connection:
            self._connection.execute(
                "DELETE FROM station_assignments WHERE product_code = ? AND version = ?",
                (product, version),
            )
            self._connection.execute(
                "UPDATE product_configurations SET bom_version_id = ? "
                "WHERE product_code = ? AND version = ?",
                (configuration.bom_version_id, product, version),
            )
            for (device_code, station_code), material_code in configuration.assignments.items():
                device = normalize_code(device_code)
                station = normalize_code(station_code)
                self._connection.execute(
                    "INSERT INTO station_assignments "
                    "(product_code, version, device_code, station_code, material_code) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (product, version, device, station, normalize_code(material_code)),
                )
                self._connection.execute(
                    "UPDATE stations SET referenced = 1 WHERE device_code = ? AND code = ?",
                    (device, station),
                )
            _write_audit(
                self._connection,
                actor=actor,
                action="UPDATE",
                entity_type="PRODUCT_CONFIGURATION",
                entity_key=f"{product}/{version}",
                before={"assignments": len(current.configuration.assignments)},
                after={"assignments": len(configuration.assignments)},
            )
        return self.get_record(product, version)

    def validate(self, configuration: ProductConfiguration) -> list[str]:
        errors: list[str] = []
        if not normalize_code(configuration.product_code):
            errors.append("Product code is required")
        if not normalize_code(configuration.version):
            errors.append("Configuration version is required")
        if not configuration.assignments:
            errors.append("Configuration must contain at least one station assignment")
        if configuration.bom_version_id is not None:
            bom = self._connection.execute(
                "SELECT product_code FROM bom_versions WHERE id = ?",
                (configuration.bom_version_id,),
            ).fetchone()
            if bom is None:
                errors.append(f"Unknown BOM version {configuration.bom_version_id}")
            elif str(bom[0]) != normalize_code(configuration.product_code):
                errors.append("BOM version belongs to a different product")
        for device, station in configuration.assignments:
            row = self._connection.execute(
                "SELECT d.enabled, d.archived, s.enabled, s.archived "
                "FROM devices d JOIN stations s ON s.device_code = d.code "
                "WHERE d.code = ? AND s.code = ?",
                (normalize_code(device), normalize_code(station)),
            ).fetchone()
            if row is None or not bool(row[0]) or bool(row[1]) or not bool(row[2]) or bool(row[3]):
                errors.append(f"Unknown or disabled station {device}/{station}")
        if configuration.bom_version_id is not None:
            for material in configuration.assignments.values():
                exists = self._connection.execute(
                    "SELECT 1 FROM bom_items WHERE bom_version_id = ? AND material_code = ?",
                    (configuration.bom_version_id, normalize_code(material)),
                ).fetchone()
                if exists is None:
                    errors.append(
                        f"Material {material} does not exist in BOM version "
                        f"{configuration.bom_version_id}"
                    )
        return errors

    def get(self, product_code: str, version: str) -> ProductConfiguration:
        return self.get_record(product_code, version).configuration

    def get_record(self, product_code: str, version: str) -> ProductConfigurationRecord:
        product = normalize_code(product_code)
        normalized_version = normalize_code(version)
        row = self._connection.execute(
            "SELECT status, bom_version_id, created_at, created_by, published_at, activated_at "
            "FROM product_configurations WHERE product_code = ? AND version = ?",
            (product, normalized_version),
        ).fetchone()
        if row is None:
            raise UnknownConfigurationError(
                f"Unknown product configuration: {product}/{normalized_version}"
            )
        assignments = {
            (str(item[0]), str(item[1])): str(item[2])
            for item in self._connection.execute(
                "SELECT device_code, station_code, material_code FROM station_assignments "
                "WHERE product_code = ? AND version = ? ORDER BY device_code, station_code",
                (product, normalized_version),
            )
        }
        configuration = ProductConfiguration(
            product,
            normalized_version,
            assignments,
            None if row[1] is None else int(row[1]),
        )
        return ProductConfigurationRecord(
            configuration,
            ConfigurationStatus(str(row[0])),
            _parse_datetime(row[2]),
            str(row[3]),
            None if row[4] is None else _parse_datetime(row[4]),
            None if row[5] is None else _parse_datetime(row[5]),
        )

    def list_configurations(self) -> list[ProductConfiguration]:
        """List only active configurations whose current master data remains enabled."""
        rows = self._connection.execute(
            "SELECT pc.product_code, pc.version FROM product_configurations pc "
            "WHERE pc.status = 'ACTIVE' "
            "AND EXISTS (SELECT 1 FROM station_assignments sa "
            "            WHERE sa.product_code = pc.product_code AND sa.version = pc.version) "
            "AND NOT EXISTS ("
            "    SELECT 1 FROM station_assignments sa "
            "    JOIN stations s ON s.device_code = sa.device_code AND s.code = sa.station_code "
            "    JOIN devices d ON d.code = sa.device_code "
            "    WHERE sa.product_code = pc.product_code AND sa.version = pc.version "
            "      AND (d.enabled = 0 OR d.archived = 1 OR s.enabled = 0 OR s.archived = 1)"
            ") ORDER BY pc.product_code, pc.version"
        )
        return [self.get(str(row[0]), str(row[1])) for row in rows]

    def list_all(self) -> list[ProductConfigurationRecord]:
        rows = self._connection.execute(
            "SELECT product_code, version FROM product_configurations "
            "ORDER BY product_code, version"
        )
        return [self.get_record(str(row[0]), str(row[1])) for row in rows]

    def publish(
        self, product_code: str, version: str, *, actor: str = "SYSTEM"
    ) -> ProductConfigurationRecord:
        record = self.get_record(product_code, version)
        errors = self.validate(record.configuration)
        if errors:
            raise InvalidLifecycleTransition("; ".join(errors))
        return self._transition(
            product_code,
            version,
            {ConfigurationStatus.DRAFT},
            ConfigurationStatus.PUBLISHED,
            actor,
        )

    def activate(
        self, product_code: str, version: str, *, actor: str = "SYSTEM"
    ) -> ProductConfigurationRecord:
        record = self.get_record(product_code, version)
        errors = self.validate(record.configuration)
        if errors:
            raise InvalidLifecycleTransition("; ".join(errors))
        return self._transition(
            product_code,
            version,
            {ConfigurationStatus.PUBLISHED, ConfigurationStatus.DISABLED},
            ConfigurationStatus.ACTIVE,
            actor,
        )

    def disable(
        self, product_code: str, version: str, *, actor: str = "SYSTEM"
    ) -> ProductConfigurationRecord:
        return self._transition(
            product_code,
            version,
            {ConfigurationStatus.ACTIVE},
            ConfigurationStatus.DISABLED,
            actor,
        )

    def archive(
        self, product_code: str, version: str, *, actor: str = "SYSTEM"
    ) -> ProductConfigurationRecord:
        return self._transition(
            product_code,
            version,
            {
                ConfigurationStatus.DRAFT,
                ConfigurationStatus.PUBLISHED,
                ConfigurationStatus.DISABLED,
            },
            ConfigurationStatus.ARCHIVED,
            actor,
        )

    def copy_version(
        self,
        product_code: str,
        version: str,
        new_version: str,
        *,
        actor: str = "SYSTEM",
    ) -> ProductConfigurationRecord:
        source = self.get(product_code, version)
        copied = replace(source, version=normalize_code(new_version))
        self.create_draft(copied, actor=actor)
        return self.get_record(product_code, new_version)

    def _transition(
        self,
        product_code: str,
        version: str,
        allowed: set[ConfigurationStatus],
        target: ConfigurationStatus,
        actor: str,
    ) -> ProductConfigurationRecord:
        current = self.get_record(product_code, version)
        if current.status not in allowed:
            raise InvalidLifecycleTransition(
                f"Configuration cannot transition from {current.status.value} to {target.value}"
            )
        timestamp_column = {
            ConfigurationStatus.PUBLISHED: "published_at",
            ConfigurationStatus.ACTIVE: "activated_at",
            ConfigurationStatus.ARCHIVED: "archived_at",
        }.get(target)
        with self._connection:
            if timestamp_column is None:
                self._connection.execute(
                    "UPDATE product_configurations SET status = ? "
                    "WHERE product_code = ? AND version = ?",
                    (target.value, normalize_code(product_code), normalize_code(version)),
                )
            elif target is ConfigurationStatus.PUBLISHED:
                self._connection.execute(
                    "UPDATE product_configurations SET status = ?, published_at = ? "
                    "WHERE product_code = ? AND version = ?",
                    (
                        target.value,
                        _iso(_utc_now()),
                        normalize_code(product_code),
                        normalize_code(version),
                    ),
                )
            elif target is ConfigurationStatus.ACTIVE:
                self._connection.execute(
                    "UPDATE product_configurations SET status = ?, activated_at = ? "
                    "WHERE product_code = ? AND version = ?",
                    (
                        target.value,
                        _iso(_utc_now()),
                        normalize_code(product_code),
                        normalize_code(version),
                    ),
                )
            else:
                self._connection.execute(
                    "UPDATE product_configurations SET status = ?, archived_at = ? "
                    "WHERE product_code = ? AND version = ?",
                    (
                        target.value,
                        _iso(_utc_now()),
                        normalize_code(product_code),
                        normalize_code(version),
                    ),
                )
            _write_audit(
                self._connection,
                actor=actor,
                action=target.value,
                entity_type="PRODUCT_CONFIGURATION",
                entity_key=f"{normalize_code(product_code)}/{normalize_code(version)}",
                before={"status": current.status.value},
                after={"status": target.value},
            )
        return self.get_record(product_code, version)

    def _exists(self, product_code: str, version: str) -> bool:
        return self._connection.execute(
            "SELECT 1 FROM product_configurations WHERE product_code = ? AND version = ?",
            (product_code, version),
        ).fetchone() is not None


class SqliteAttemptRepository:
    """Append and query immutable verification attempt history."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def append(self, attempt: Attempt) -> Attempt:
        with self._connection:
            return self._insert(attempt)

    def _insert(self, attempt: Attempt) -> Attempt:
        cursor = self._connection.execute(
            "INSERT INTO attempts "
            "(timestamp, run_id, product_code, product_version, device_code, station_code, "
            "expected_material, scanned_material, result, repeated) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                attempt.timestamp.isoformat(),
                attempt.run_id,
                attempt.product_code,
                attempt.product_version,
                attempt.device_code,
                attempt.station_code,
                attempt.expected_material,
                attempt.scanned_material,
                attempt.result.value,
                int(attempt.repeated),
            ),
        )
        if cursor.lastrowid is None:
            raise RuntimeError("SQLite did not allocate an attempt identifier")
        return replace(attempt, id=cursor.lastrowid)

    def list_for_run(self, run_id: str) -> list[Attempt]:
        rows = self._connection.execute(
            "SELECT id, timestamp, run_id, product_code, product_version, device_code, "
            "station_code, expected_material, scanned_material, result, repeated "
            "FROM attempts WHERE run_id = ? ORDER BY id",
            (run_id,),
        )
        return [self._map_attempt(row) for row in rows]

    @staticmethod
    def _map_attempt(row: sqlite3.Row | tuple[object, ...]) -> Attempt:
        return Attempt(
            id=int(str(row[0])),
            timestamp=datetime.fromisoformat(str(row[1])),
            run_id=str(row[2]),
            product_code=str(row[3]),
            product_version=str(row[4]),
            device_code=str(row[5]),
            station_code=str(row[6]),
            expected_material=str(row[7]),
            scanned_material=str(row[8]),
            result=VerificationResult(str(row[9])),
            repeated=bool(row[10]),
        )


class SqliteProductionRunRepository(SqliteAttemptRepository):
    """Persist run headers, snapshots, station state, and attempts atomically."""

    def start(
        self,
        run_id: str,
        configuration: ProductConfiguration,
        *,
        operator: str,
        started_at: datetime,
    ) -> ProductionRun:
        normalized_run_id = normalize_code(run_id)
        if not normalized_run_id:
            raise ValueError("Run identifier is required")
        if not configuration.assignments:
            raise ValueError("Cannot start a run with an empty configuration")
        snapshot = {
            "bom_version_id": configuration.bom_version_id,
            "assignments": [
                {
                    "device_code": device,
                    "station_code": station,
                    "material_code": material,
                }
                for (device, station), material in sorted(configuration.assignments.items())
            ],
        }
        try:
            with self._connection:
                self._connection.execute(
                    "INSERT INTO production_runs "
                    "(run_id, product_code, product_version, configuration_snapshot, operator, "
                    "status, started_at) VALUES (?, ?, ?, ?, ?, 'RUNNING', ?)",
                    (
                        normalized_run_id,
                        configuration.product_code,
                        configuration.version,
                        _json(snapshot),
                        operator.strip() or "SYSTEM",
                        _iso(started_at),
                    ),
                )
                for (device, station), material in configuration.assignments.items():
                    self._connection.execute(
                        "INSERT INTO run_station_states "
                        "(run_id, device_code, station_code, expected_material, status) "
                        "VALUES (?, ?, ?, ?, 'PENDING')",
                        (normalized_run_id, device, station, material),
                    )
                _write_audit(
                    self._connection,
                    actor=operator,
                    action="START",
                    entity_type="PRODUCTION_RUN",
                    entity_key=normalized_run_id,
                    after={
                        "product_code": configuration.product_code,
                        "product_version": configuration.version,
                        "station_count": len(configuration.assignments),
                    },
                    timestamp=started_at,
                )
        except sqlite3.IntegrityError as error:
            raise InvalidLifecycleTransition(
                f"Cannot start production run {normalized_run_id}"
            ) from error
        return self.get(normalized_run_id)

    def record_attempt(self, attempt: Attempt) -> Attempt:
        with self._connection:
            row = self._connection.execute(
                "SELECT status, product_code, product_version FROM production_runs "
                "WHERE run_id = ?",
                (attempt.run_id,),
            ).fetchone()
            if row is None:
                raise UnknownRunError(f"Unknown production run: {attempt.run_id}")
            if str(row[0]) != RunStatus.RUNNING.value:
                raise InvalidLifecycleTransition(
                    f"Production run is not active: {attempt.run_id}"
                )
            if (str(row[1]), str(row[2])) != (
                attempt.product_code,
                attempt.product_version,
            ):
                raise InvalidLifecycleTransition(
                    "Attempt configuration does not match run snapshot"
                )
            station = self._connection.execute(
                "SELECT expected_material, status FROM run_station_states "
                "WHERE run_id = ? AND device_code = ? AND station_code = ?",
                (attempt.run_id, attempt.device_code, attempt.station_code),
            ).fetchone()
            if station is None or str(station[0]) != attempt.expected_material:
                raise InvalidLifecycleTransition("Attempt station does not match run snapshot")
            stored = self._insert(attempt)
            if attempt.result is VerificationResult.OK and str(station[1]) == "PENDING":
                self._connection.execute(
                    "UPDATE run_station_states SET status = 'COMPLETED', completed_at = ? "
                    "WHERE run_id = ? AND device_code = ? AND station_code = ?",
                    (
                        _iso(attempt.timestamp),
                        attempt.run_id,
                        attempt.device_code,
                        attempt.station_code,
                    ),
                )
                remaining = int(
                    self._connection.execute(
                        "SELECT COUNT(*) FROM run_station_states "
                        "WHERE run_id = ? AND status = 'PENDING'",
                        (attempt.run_id,),
                    ).fetchone()[0]
                )
                if remaining == 0:
                    self._connection.execute(
                        "UPDATE production_runs SET status = 'COMPLETED', completed_at = ? "
                        "WHERE run_id = ?",
                        (_iso(attempt.timestamp), attempt.run_id),
                    )
                    _write_audit(
                        self._connection,
                        actor=self.get(attempt.run_id).operator,
                        action="COMPLETE",
                        entity_type="PRODUCTION_RUN",
                        entity_key=attempt.run_id,
                        after={"status": RunStatus.COMPLETED.value},
                        timestamp=attempt.timestamp,
                    )
            return stored

    def get(self, run_id: str) -> ProductionRun:
        row = self._connection.execute(
            "SELECT run_id, product_code, product_version, configuration_snapshot, operator, "
            "status, started_at, completed_at, interrupted_at, interruption_reason "
            "FROM production_runs WHERE run_id = ?",
            (normalize_code(run_id),),
        ).fetchone()
        if row is None:
            raise UnknownRunError(f"Unknown production run: {run_id}")
        decoded_snapshot: object = json.loads(str(row[3]))
        if not isinstance(decoded_snapshot, dict):
            raise RuntimeError("Invalid production run configuration snapshot")
        snapshot = cast(dict[str, object], decoded_snapshot)
        raw_assignments = snapshot.get("assignments")
        if not isinstance(raw_assignments, list):
            raise RuntimeError("Invalid production run station snapshot")
        assignments: dict[tuple[str, str], str] = {}
        for raw_item in cast(list[object], raw_assignments):
            if not isinstance(raw_item, dict):
                raise RuntimeError("Invalid production run assignment snapshot")
            item = cast(dict[str, object], raw_item)
            assignments[(str(item["device_code"]), str(item["station_code"]))] = str(
                item["material_code"]
            )
        raw_bom_version_id = snapshot.get("bom_version_id")
        configuration = ProductConfiguration(
            str(row[1]),
            str(row[2]),
            assignments,
            None if raw_bom_version_id is None else int(str(raw_bom_version_id)),
        )
        progress = self._connection.execute(
            "SELECT SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END), COUNT(*) "
            "FROM run_station_states WHERE run_id = ?",
            (str(row[0]),),
        ).fetchone()
        return ProductionRun(
            run_id=str(row[0]),
            configuration=configuration,
            operator=str(row[4]),
            status=RunStatus(str(row[5])),
            started_at=_parse_datetime(row[6]),
            completed_stations=int(progress[0] or 0),
            total_stations=int(progress[1]),
            completed_at=None if row[7] is None else _parse_datetime(row[7]),
            interrupted_at=None if row[8] is None else _parse_datetime(row[8]),
            interruption_reason=str(row[9]),
        )

    def list_runs(self, status: RunStatus | None = None) -> list[ProductionRun]:
        if status is None:
            rows = self._connection.execute(
                "SELECT run_id FROM production_runs ORDER BY started_at, run_id"
            )
        else:
            rows = self._connection.execute(
                "SELECT run_id FROM production_runs WHERE status = ? ORDER BY started_at, run_id",
                (status.value,),
            )
        return [self.get(str(row[0])) for row in rows]

    def search_runs(
        self,
        query: str = "",
        *,
        operator: str = "",
        status: RunStatus | None = None,
        started_from: datetime | None = None,
        started_to: datetime | None = None,
    ) -> list[ProductionRun]:
        """Filter persisted runs for the management page."""
        pattern = f"%{query.strip()}%"
        operator_pattern = f"%{operator.strip()}%"
        rows = self._connection.execute(
            "SELECT run_id FROM production_runs "
            "WHERE (? = '%%' OR run_id LIKE ? OR product_code LIKE ? OR product_version LIKE ?) "
            "AND (? = '%%' OR operator LIKE ?) "
            "AND (? IS NULL OR status = ?) "
            "AND (? IS NULL OR started_at >= ?) "
            "AND (? IS NULL OR started_at <= ?) "
            "ORDER BY started_at DESC, run_id DESC",
            (
                pattern,
                pattern,
                pattern,
                pattern,
                operator_pattern,
                operator_pattern,
                None if status is None else status.value,
                None if status is None else status.value,
                None if started_from is None else _iso(started_from),
                None if started_from is None else _iso(started_from),
                None if started_to is None else _iso(started_to),
                None if started_to is None else _iso(started_to),
            ),
        )
        return [self.get(str(row[0])) for row in rows]

    def list_station_states(self, run_id: str) -> list[RunStationState]:
        """Return immutable snapshot station state in display order."""
        self.get(run_id)
        rows = self._connection.execute(
            "SELECT device_code, station_code, expected_material, status, completed_at "
            "FROM run_station_states WHERE run_id = ? ORDER BY device_code, station_code",
            (normalize_code(run_id),),
        )
        return [
            RunStationState(
                str(row[0]),
                str(row[1]),
                str(row[2]),
                str(row[3]) == "COMPLETED",
                None if row[4] is None else _parse_datetime(row[4]),
            )
            for row in rows
        ]

    def completed_station_keys(self, run_id: str) -> set[tuple[str, str]]:
        return {
            (str(row[0]), str(row[1]))
            for row in self._connection.execute(
                "SELECT device_code, station_code FROM run_station_states "
                "WHERE run_id = ? AND status = 'COMPLETED'",
                (normalize_code(run_id),),
            )
        }

    def interrupt(
        self,
        run_id: str,
        *,
        operator: str,
        interrupted_at: datetime,
        reason: str,
    ) -> None:
        current = self.get(run_id)
        if current.status is not RunStatus.RUNNING:
            raise InvalidLifecycleTransition(f"Production run is not active: {run_id}")
        with self._connection:
            self._connection.execute(
                "UPDATE production_runs SET status = 'INTERRUPTED', interrupted_at = ?, "
                "interruption_reason = ? WHERE run_id = ?",
                (_iso(interrupted_at), reason.strip(), current.run_id),
            )
            _write_audit(
                self._connection,
                actor=operator,
                action="INTERRUPT",
                entity_type="PRODUCTION_RUN",
                entity_key=current.run_id,
                before={"status": current.status.value},
                after={"status": RunStatus.INTERRUPTED.value, "reason": reason.strip()},
                timestamp=interrupted_at,
            )

    def resume(
        self, run_id: str, *, operator: str, resumed_at: datetime
    ) -> ProductionRun:
        current = self.get(run_id)
        if current.status is not RunStatus.INTERRUPTED:
            raise InvalidLifecycleTransition(f"Production run is not interrupted: {run_id}")
        with self._connection:
            self._connection.execute(
                "UPDATE production_runs SET status = 'RUNNING', operator = ?, "
                "interrupted_at = NULL, interruption_reason = '' WHERE run_id = ?",
                (operator.strip() or "SYSTEM", current.run_id),
            )
            _write_audit(
                self._connection,
                actor=operator,
                action="RESUME",
                entity_type="PRODUCTION_RUN",
                entity_key=current.run_id,
                before={"status": current.status.value, "operator": current.operator},
                after={
                    "status": RunStatus.RUNNING.value,
                    "operator": operator.strip() or "SYSTEM",
                },
                timestamp=resumed_at,
            )
        return self.get(current.run_id)


class SqliteAuditRepository:
    """Query append-only audit history without exposing mutation methods."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def list_for_entity(self, entity_type: str, entity_key: str) -> list[AuditEntry]:
        rows = self._connection.execute(
            "SELECT id, timestamp, actor, action, entity_type, entity_key, before_json, after_json "
            "FROM audit_logs WHERE entity_type = ? AND entity_key = ? ORDER BY id",
            (entity_type, entity_key),
        )
        return [
            AuditEntry(
                int(row[0]),
                _parse_datetime(row[1]),
                str(row[2]),
                str(row[3]),
                str(row[4]),
                str(row[5]),
                None if row[6] is None else str(row[6]),
                None if row[7] is None else str(row[7]),
            )
            for row in rows
        ]

    def search(
        self,
        *,
        entity_type: str = "",
        entity_key: str = "",
        actor: str = "",
        action: str = "",
        started_from: datetime | None = None,
        started_to: datetime | None = None,
        limit: int = 1000,
    ) -> list[AuditEntry]:
        """Search immutable audit history using combinable filters."""
        if limit < 1:
            raise ValueError("Audit query limit must be positive")
        rows = self._connection.execute(
            "SELECT id, timestamp, actor, action, entity_type, entity_key, before_json, after_json "
            "FROM audit_logs WHERE (? = '' OR entity_type = ?) "
            "AND (? = '' OR entity_key LIKE ?) AND (? = '' OR actor LIKE ?) "
            "AND (? = '' OR action = ?) AND (? IS NULL OR timestamp >= ?) "
            "AND (? IS NULL OR timestamp <= ?) ORDER BY id DESC LIMIT ?",
            (
                entity_type.strip(),
                entity_type.strip(),
                entity_key.strip(),
                f"%{entity_key.strip()}%",
                actor.strip(),
                f"%{actor.strip()}%",
                action.strip(),
                action.strip(),
                None if started_from is None else _iso(started_from),
                None if started_from is None else _iso(started_from),
                None if started_to is None else _iso(started_to),
                None if started_to is None else _iso(started_to),
                limit,
            ),
        )
        return [
            AuditEntry(
                int(row[0]),
                _parse_datetime(row[1]),
                str(row[2]),
                str(row[3]),
                str(row[4]),
                str(row[5]),
                None if row[6] is None else str(row[6]),
                None if row[7] is None else str(row[7]),
            )
            for row in rows
        ]
