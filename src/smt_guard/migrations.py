"""Ordered, immutable SQLite schema migrations."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Migration:
    """One forward schema migration with an explicit rollback policy."""

    version: int
    name: str
    up_sql: str
    down_sql: str | None = None
    irreversible_reason: str | None = None


MIGRATIONS = (
    Migration(
        1,
        "initial_schema",
        """
        CREATE TABLE devices (
            code TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            line TEXT NOT NULL,
            enabled INTEGER NOT NULL CHECK (enabled IN (0, 1))
        );

        CREATE TABLE stations (
            device_code TEXT NOT NULL,
            code TEXT NOT NULL,
            enabled INTEGER NOT NULL CHECK (enabled IN (0, 1)),
            referenced INTEGER NOT NULL CHECK (referenced IN (0, 1)),
            PRIMARY KEY (device_code, code),
            FOREIGN KEY (device_code) REFERENCES devices(code) ON DELETE RESTRICT
        );

        CREATE TABLE product_configurations (
            product_code TEXT NOT NULL,
            version TEXT NOT NULL,
            PRIMARY KEY (product_code, version)
        );

        CREATE TABLE station_assignments (
            product_code TEXT NOT NULL,
            version TEXT NOT NULL,
            device_code TEXT NOT NULL,
            station_code TEXT NOT NULL,
            material_code TEXT NOT NULL,
            PRIMARY KEY (product_code, version, device_code, station_code),
            FOREIGN KEY (product_code, version)
                REFERENCES product_configurations(product_code, version) ON DELETE CASCADE,
            FOREIGN KEY (device_code, station_code)
                REFERENCES stations(device_code, code) ON DELETE RESTRICT
        );

        CREATE TABLE attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            run_id TEXT NOT NULL,
            product_code TEXT NOT NULL,
            product_version TEXT NOT NULL,
            device_code TEXT NOT NULL,
            station_code TEXT NOT NULL,
            expected_material TEXT NOT NULL,
            scanned_material TEXT NOT NULL,
            result TEXT NOT NULL CHECK (result IN ('OK', 'NG')),
            repeated INTEGER NOT NULL CHECK (repeated IN (0, 1))
        );

        CREATE INDEX attempts_run_id_id ON attempts(run_id, id);
        """,
        irreversible_reason="Initial schema removal would destroy application data.",
    ),
    Migration(
        2,
        "persistent_lifecycle_models",
        """
        ALTER TABLE devices ADD COLUMN archived INTEGER NOT NULL DEFAULT 0
            CHECK (archived IN (0, 1));
        ALTER TABLE devices ADD COLUMN created_at TEXT NOT NULL DEFAULT '';
        ALTER TABLE devices ADD COLUMN updated_at TEXT NOT NULL DEFAULT '';

        ALTER TABLE stations ADD COLUMN name TEXT NOT NULL DEFAULT '';
        ALTER TABLE stations ADD COLUMN archived INTEGER NOT NULL DEFAULT 0
            CHECK (archived IN (0, 1));
        ALTER TABLE stations ADD COLUMN created_at TEXT NOT NULL DEFAULT '';
        ALTER TABLE stations ADD COLUMN updated_at TEXT NOT NULL DEFAULT '';

        CREATE TABLE bom_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_code TEXT NOT NULL,
            version TEXT NOT NULL,
            bom_number TEXT NOT NULL,
            bom_name TEXT NOT NULL,
            product_name TEXT NOT NULL,
            product_specification TEXT NOT NULL,
            status TEXT NOT NULL CHECK (
                status IN ('DRAFT', 'PUBLISHED', 'ACTIVE', 'OBSOLETE', 'ARCHIVED')
            ),
            source_filename TEXT NOT NULL,
            source_sha256 TEXT NOT NULL,
            imported_at TEXT NOT NULL,
            imported_by TEXT NOT NULL,
            published_at TEXT,
            activated_at TEXT,
            UNIQUE (product_code, version)
        );

        CREATE TABLE bom_items (
            bom_version_id INTEGER NOT NULL,
            material_code TEXT NOT NULL,
            name TEXT NOT NULL,
            specification TEXT NOT NULL,
            quantity TEXT NOT NULL,
            category TEXT NOT NULL,
            PRIMARY KEY (bom_version_id, material_code),
            FOREIGN KEY (bom_version_id) REFERENCES bom_versions(id) ON DELETE RESTRICT
        );

        CREATE UNIQUE INDEX one_active_bom_per_product
            ON bom_versions(product_code) WHERE status = 'ACTIVE';

        ALTER TABLE product_configurations ADD COLUMN status TEXT NOT NULL DEFAULT 'ACTIVE'
            CHECK (status IN ('DRAFT', 'PUBLISHED', 'ACTIVE', 'DISABLED', 'ARCHIVED'));
        ALTER TABLE product_configurations ADD COLUMN bom_version_id INTEGER
            REFERENCES bom_versions(id) ON DELETE RESTRICT;
        ALTER TABLE product_configurations ADD COLUMN created_at TEXT NOT NULL DEFAULT '';
        ALTER TABLE product_configurations ADD COLUMN created_by TEXT NOT NULL DEFAULT 'legacy';
        ALTER TABLE product_configurations ADD COLUMN published_at TEXT;
        ALTER TABLE product_configurations ADD COLUMN activated_at TEXT;
        ALTER TABLE product_configurations ADD COLUMN archived_at TEXT;

        CREATE TABLE production_runs (
            run_id TEXT PRIMARY KEY,
            product_code TEXT NOT NULL,
            product_version TEXT NOT NULL,
            configuration_snapshot TEXT NOT NULL,
            operator TEXT NOT NULL,
            status TEXT NOT NULL CHECK (
                status IN ('RUNNING', 'COMPLETED', 'INTERRUPTED')
            ),
            started_at TEXT NOT NULL,
            completed_at TEXT,
            interrupted_at TEXT,
            interruption_reason TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (product_code, product_version)
                REFERENCES product_configurations(product_code, version) ON DELETE RESTRICT
        );

        CREATE TABLE run_station_states (
            run_id TEXT NOT NULL,
            device_code TEXT NOT NULL,
            station_code TEXT NOT NULL,
            expected_material TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('PENDING', 'COMPLETED')),
            completed_at TEXT,
            PRIMARY KEY (run_id, device_code, station_code),
            FOREIGN KEY (run_id) REFERENCES production_runs(run_id) ON DELETE RESTRICT,
            FOREIGN KEY (device_code, station_code)
                REFERENCES stations(device_code, code) ON DELETE RESTRICT
        );

        CREATE INDEX production_runs_status_started
            ON production_runs(status, started_at);

        CREATE TABLE audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            actor TEXT NOT NULL,
            action TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_key TEXT NOT NULL,
            before_json TEXT,
            after_json TEXT
        );

        CREATE INDEX audit_logs_entity
            ON audit_logs(entity_type, entity_key, id);

        CREATE TRIGGER attempts_no_update
        BEFORE UPDATE ON attempts
        BEGIN
            SELECT RAISE(ABORT, 'attempts are append-only');
        END;

        CREATE TRIGGER attempts_no_delete
        BEFORE DELETE ON attempts
        BEGIN
            SELECT RAISE(ABORT, 'attempts are append-only');
        END;

        CREATE TRIGGER audit_logs_no_update
        BEFORE UPDATE ON audit_logs
        BEGIN
            SELECT RAISE(ABORT, 'audit logs are append-only');
        END;

        CREATE TRIGGER audit_logs_no_delete
        BEFORE DELETE ON audit_logs
        BEGIN
            SELECT RAISE(ABORT, 'audit logs are append-only');
        END;

        CREATE TRIGGER published_bom_items_no_insert
        BEFORE INSERT ON bom_items
        WHEN (SELECT status FROM bom_versions WHERE id = NEW.bom_version_id) <> 'DRAFT'
        BEGIN
            SELECT RAISE(ABORT, 'published BOM is immutable');
        END;

        CREATE TRIGGER published_bom_items_no_update
        BEFORE UPDATE ON bom_items
        WHEN (SELECT status FROM bom_versions WHERE id = OLD.bom_version_id) <> 'DRAFT'
        BEGIN
            SELECT RAISE(ABORT, 'published BOM is immutable');
        END;

        CREATE TRIGGER published_bom_items_no_delete
        BEFORE DELETE ON bom_items
        WHEN (SELECT status FROM bom_versions WHERE id = OLD.bom_version_id) <> 'DRAFT'
        BEGIN
            SELECT RAISE(ABORT, 'published BOM is immutable');
        END;

        CREATE TRIGGER released_assignments_no_insert
        BEFORE INSERT ON station_assignments
        WHEN (SELECT status FROM product_configurations
              WHERE product_code = NEW.product_code AND version = NEW.version) <> 'DRAFT'
        BEGIN
            SELECT RAISE(ABORT, 'released configuration is immutable');
        END;

        CREATE TRIGGER released_assignments_no_update
        BEFORE UPDATE ON station_assignments
        WHEN (SELECT status FROM product_configurations
              WHERE product_code = OLD.product_code AND version = OLD.version) <> 'DRAFT'
        BEGIN
            SELECT RAISE(ABORT, 'released configuration is immutable');
        END;

        CREATE TRIGGER released_assignments_no_delete
        BEFORE DELETE ON station_assignments
        WHEN (SELECT status FROM product_configurations
              WHERE product_code = OLD.product_code AND version = OLD.version) <> 'DRAFT'
        BEGIN
            SELECT RAISE(ABORT, 'released configuration is immutable');
        END;
        """,
        irreversible_reason=(
            "Lifecycle migration adds immutable operational records; downgrade would lose them."
        ),
    ),
)
