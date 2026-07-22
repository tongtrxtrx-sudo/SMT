import sqlite3
import unittest
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from smt_guard.bom import BomDocument, BomStatus, Material, Product
from smt_guard.configuration import ConfigurationStatus
from smt_guard.scan import ProductConfiguration
from smt_guard.sqlite import (
    SqliteAuditRepository,
    SqliteBomRepository,
    SqliteDatabase,
    SqliteMasterDataRepository,
    SqliteProductConfigurationRepository,
)


class SqliteLifecycleModelTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.connection = sqlite3.connect(":memory:")
        self.addCleanup(self.connection.close)
        SqliteDatabase(self.connection).initialize()
        self.master = SqliteMasterDataRepository(self.connection)
        self.master.add_device("SMT-01", "Machine 1", "Line A", actor="ADMIN")
        self.master.add_station("SMT-01", "F-01", actor="ADMIN")

    @staticmethod
    def document(material_code: str = "013000081") -> BomDocument:
        return BomDocument(
            Product("501000087", "BOM-V1", "Board BOM", "Board", "Main"),
            {
                material_code: Material(
                    material_code, "Resistor", "1206", "1", "Electronic"
                )
            },
        )

    def test_persists_bom_provenance_and_lifecycle(self) -> None:
        source = self.directory / "bom-v1.xlsx"
        source.write_bytes(b"immutable source bytes")
        repository = SqliteBomRepository(self.connection)

        draft = repository.import_document(
            self.document(),
            source,
            operator="OP-01",
            imported_at=datetime(2026, 7, 14, 9, 0, tzinfo=UTC),
        )
        published = repository.publish("501000087", "BOM-V1", actor="OP-01")
        active = repository.activate("501000087", "BOM-V1", actor="OP-01")

        self.assertEqual(BomStatus.DRAFT, draft.status)
        self.assertEqual(BomStatus.PUBLISHED, published.status)
        self.assertEqual(BomStatus.ACTIVE, active.status)
        self.assertEqual("bom-v1.xlsx", active.source_filename)
        self.assertEqual(64, len(active.source_sha256))
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "UPDATE bom_items SET quantity = '2' WHERE bom_version_id = ?", (active.id,)
            )

    def test_configuration_draft_publish_enable_disable_archive(self) -> None:
        repository = SqliteProductConfigurationRepository(self.connection)
        configuration = ProductConfiguration(
            "501000087", "V1", {("SMT-01", "F-01"): "013000081"}
        )

        repository.create_draft(configuration, actor="ENGINEER")
        self.assertEqual(
            ConfigurationStatus.DRAFT,
            repository.get_record("501000087", "V1").status,
        )
        repository.publish("501000087", "V1", actor="ENGINEER")
        repository.activate("501000087", "V1", actor="ENGINEER")
        repository.disable("501000087", "V1", actor="ENGINEER")
        archived = repository.archive("501000087", "V1", actor="ENGINEER")

        self.assertEqual(ConfigurationStatus.ARCHIVED, archived.status)
        self.assertEqual([], repository.list_configurations())
        restored = repository.activate("501000087", "V1", actor="ENGINEER")
        self.assertEqual(ConfigurationStatus.ACTIVE, restored.status)
        self.assertEqual([configuration], repository.list_configurations())

    def test_failed_configuration_save_has_no_reference_side_effect(self) -> None:
        repository = SqliteProductConfigurationRepository(self.connection)
        self.master.add_station("SMT-01", "F-02")
        self.connection.execute(
            "CREATE TRIGGER fail_second_assignment BEFORE INSERT ON station_assignments "
            "WHEN NEW.station_code = 'F-02' "
            "BEGIN SELECT RAISE(ABORT, 'simulated configuration write failure'); END"
        )
        invalid = ProductConfiguration(
            "501000087",
            "V1",
            {
                ("SMT-01", "F-01"): "013000081",
                ("SMT-01", "F-02"): "005000103",
            },
        )

        with self.assertRaises(sqlite3.IntegrityError):
            repository.save(invalid)

        self.assertFalse(self.master.get_station("SMT-01", "F-01").referenced)
        self.assertFalse(self.master.get_station("SMT-01", "F-02").referenced)
        self.assertEqual([], repository.list_all())

    def test_master_data_changes_are_audited_and_audit_is_append_only(self) -> None:
        self.master.disable_station("SMT-01", "F-01", actor="ADMIN")
        audits = SqliteAuditRepository(self.connection).list_for_entity(
            "STATION", "SMT-01/F-01"
        )

        self.assertEqual(["CREATE", "DISABLE"], [entry.action for entry in audits])
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute("DELETE FROM audit_logs WHERE id = ?", (audits[0].id,))

    def test_master_data_supports_update_filter_enable_archive_and_safe_delete(self) -> None:
        updated = self.master.update_device(
            "SMT-01", name="Machine One", line="Line B", actor="ADMIN"
        )
        station = self.master.update_station(
            "SMT-01", "F-01", name="Front feeder", actor="ADMIN"
        )
        self.assertEqual("Machine One", updated.name)
        self.assertEqual("Front feeder", station.name)
        self.assertEqual(
            ["SMT-01"], [item.code for item in self.master.search_devices("Line B")]
        )
        self.assertEqual(
            ["F-01"],
            [item.code for item in self.master.search_stations("SMT-01", "Front")],
        )

        self.master.disable_device("SMT-01")
        self.assertEqual([], self.master.search_devices(enabled=True))
        self.master.enable_device("SMT-01")
        self.master.disable_station("SMT-01", "F-01")
        self.master.enable_station("SMT-01", "F-01")
        self.master.archive_station("SMT-01", "F-01")
        self.assertEqual([], self.master.search_stations("SMT-01"))
        self.assertEqual(
            ["F-01"],
            [
                item.code
                for item in self.master.search_stations("SMT-01", include_archived=True)
            ],
        )

        self.master.add_device("SMT-EMPTY", "Empty", "Line C")
        self.master.delete_device("SMT-EMPTY", actor="ADMIN")
        self.master.add_station("SMT-01", "F-TEMP")
        self.master.delete_station("SMT-01", "F-TEMP", actor="ADMIN")

    def test_compares_obsoletes_and_archives_bom_versions(self) -> None:
        repository = SqliteBomRepository(self.connection)
        first_source = self.directory / "bom-v1.xlsx"
        second_source = self.directory / "bom-v2.xlsx"
        first_source.write_bytes(b"version one")
        second_source.write_bytes(b"version two")
        first = repository.import_document(
            self.document("013000081"),
            first_source,
            version="V1",
            operator="OP-01",
            imported_at=datetime(2026, 7, 14, 9, 0, tzinfo=UTC),
        )
        second = repository.import_document(
            self.document("005000103"),
            second_source,
            version="V2",
            operator="OP-01",
            imported_at=datetime(2026, 7, 14, 10, 0, tzinfo=UTC),
        )

        comparison = repository.compare(first.id, second.id)
        self.assertEqual(["005000103"], comparison["added"])
        self.assertEqual(["013000081"], comparison["removed"])
        repository.publish("501000087", "V2")
        repository.activate("501000087", "V2")
        obsolete = repository.obsolete("501000087", "V2")
        archived = repository.archive("501000087", "V2")
        restored = repository.activate("501000087", "V2")

        self.assertEqual(BomStatus.OBSOLETE, obsolete.status)
        self.assertEqual(BomStatus.ARCHIVED, archived.status)
        self.assertEqual(BomStatus.ACTIVE, restored.status)
        self.assertEqual(["V1", "V2"], [item.version for item in repository.list_versions()])

    def test_copies_released_configuration_into_new_draft_version(self) -> None:
        repository = SqliteProductConfigurationRepository(self.connection)
        repository.save(
            ProductConfiguration(
                "501000087", "V1", {("SMT-01", "F-01"): "013000081"}
            )
        )

        copied = repository.copy_version("501000087", "V1", "V2", actor="ENGINEER")

        self.assertEqual(ConfigurationStatus.DRAFT, copied.status)
        self.assertEqual("013000081", copied.configuration.required_material("SMT-01", "F-01"))

    def test_edits_only_draft_configuration_and_audits_actor(self) -> None:
        repository = SqliteProductConfigurationRepository(self.connection)
        repository.create_draft(
            ProductConfiguration(
                "501000087", "V1", {("SMT-01", "F-01"): "013000081"}
            ),
            actor="ENGINEER",
        )

        updated = repository.update_draft(
            ProductConfiguration(
                "501000087", "V1", {("SMT-01", "F-01"): "005000103"}
            ),
            actor="ENGINEER-2",
        )
        self.assertEqual(
            "005000103",
            updated.configuration.required_material("SMT-01", "F-01"),
        )
        repository.publish("501000087", "V1")
        with self.assertRaisesRegex(ValueError, "draft"):
            repository.update_draft(updated.configuration)
        audits = SqliteAuditRepository(self.connection).search(
            entity_type="PRODUCT_CONFIGURATION", actor="ENGINEER-2", action="UPDATE"
        )
        self.assertEqual(1, len(audits))


if __name__ == "__main__":
    unittest.main()
