import sqlite3
import unittest

from smt_guard.migrations import MIGRATIONS, Migration
from smt_guard.sqlite import MigrationError, SqliteDatabase


class SqliteSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.addCleanup(self.connection.close)

    def test_initializes_versioned_schema_and_foreign_keys(self) -> None:
        SqliteDatabase(self.connection).initialize()

        tables = {
            row[0]
            for row in self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

        self.assertTrue(
            {"devices", "stations", "product_configurations", "station_assignments", "attempts"}
            <= tables
        )
        self.assertTrue(
            {"schema_migrations", "bom_versions", "bom_items", "production_runs", 
             "run_station_states", "audit_logs", "job_number_sequences"} <= tables
        )
        applied = self.connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()
        self.assertEqual([(1,), (2,), (3,), (4,)], applied)
        self.assertEqual(4, self.connection.execute("PRAGMA user_version").fetchone()[0])
        self.assertEqual(1, self.connection.execute("PRAGMA foreign_keys").fetchone()[0])

    def test_initialization_is_idempotent_and_preserves_data(self) -> None:
        database = SqliteDatabase(self.connection)
        database.initialize()
        self.connection.execute(
            "INSERT INTO devices (code, name, line, enabled) VALUES (?, ?, ?, ?)",
            ("SMT-01", "Machine 1", "Line A", 1),
        )
        self.connection.commit()

        database.initialize()

        row = self.connection.execute("SELECT code, name FROM devices").fetchone()
        self.assertEqual(("SMT-01", "Machine 1"), row)

    def test_backup_restore_preserves_historical_bom_links(self) -> None:
        SqliteDatabase(self.connection).initialize()
        self.connection.execute(
            "INSERT INTO devices (code, name, line, enabled) VALUES (?, ?, ?, ?)",
            ("SMT-01", "Machine 1", "Line A", 1),
        )
        self.connection.execute(
            "INSERT INTO stations (device_code, code, enabled, referenced) "
            "VALUES (?, ?, ?, ?)",
            ("SMT-01", "F-01", 1, 1),
        )
        cursor = self.connection.execute(
            "INSERT INTO bom_versions ("
            "product_code, version, bom_number, bom_name, product_name, "
            "product_specification, status, source_filename, source_sha256, "
            "imported_at, imported_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "501000087",
                "BOM-V1",
                "BOM-1",
                "Historical BOM",
                "Board",
                "Spec",
                "DRAFT",
                "legacy.xlsx",
                "abc123",
                "2026-07-20T00:00:00+00:00",
                "OP-01",
            ),
        )
        bom_id = cursor.lastrowid
        assert bom_id is not None
        self.connection.execute(
            "INSERT INTO bom_items "
            "(bom_version_id, material_code, name, specification, quantity, category) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (bom_id, "M-1", "Material", "Spec", "1", "Main"),
        )
        self.connection.execute(
            "UPDATE bom_versions SET status = 'ACTIVE' WHERE id = ?",
            (bom_id,),
        )
        self.connection.execute(
            "INSERT INTO product_configurations "
            "(product_code, version, status, bom_version_id) VALUES (?, ?, ?, ?)",
            ("501000087", "V1", "DRAFT", bom_id),
        )
        self.connection.execute(
            "INSERT INTO station_assignments "
            "(product_code, version, device_code, station_code, material_code) "
            "VALUES (?, ?, ?, ?, ?)",
            ("501000087", "V1", "SMT-01", "F-01", "M-1"),
        )
        self.connection.execute(
            "UPDATE product_configurations SET status = 'ACTIVE' "
            "WHERE product_code = ? AND version = ?",
            ("501000087", "V1"),
        )
        self.connection.commit()

        restored = sqlite3.connect(":memory:")
        self.addCleanup(restored.close)
        self.connection.backup(restored)
        SqliteDatabase(restored).initialize()

        self.assertEqual(("ok",), restored.execute("PRAGMA quick_check").fetchone())
        self.assertEqual(
            (bom_id, "M-1"),
            restored.execute(
                "SELECT pc.bom_version_id, bi.material_code "
                "FROM product_configurations pc "
                "JOIN bom_items bi ON bi.bom_version_id = pc.bom_version_id "
                "WHERE pc.product_code = ? AND pc.version = ?",
                ("501000087", "V1"),
            ).fetchone(),
        )

    def test_station_requires_an_existing_device(self) -> None:
        SqliteDatabase(self.connection).initialize()

        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO stations (device_code, code, enabled, referenced) "
                "VALUES (?, ?, ?, ?)",
                ("SMT-99", "F-01", 1, 0),
            )

    def test_station_code_is_unique_across_all_devices(self) -> None:
        SqliteDatabase(self.connection).initialize()
        self.connection.executemany(
            "INSERT INTO devices (code, name, line, enabled) VALUES (?, ?, ?, ?)",
            [
                ("SMT-01", "Machine 1", "Line A", 1),
                ("SMT-02", "Machine 2", "Line A", 1),
            ],
        )
        self.connection.execute(
            "INSERT INTO stations (device_code, code, enabled, referenced) "
            "VALUES (?, ?, ?, ?)",
            ("SMT-01", "F-01", 1, 0),
        )

        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO stations (device_code, code, enabled, referenced) "
                "VALUES (?, ?, ?, ?)",
                ("SMT-02", "F-01", 1, 0),
            )

    def test_upgrades_legacy_v1_database_without_losing_data(self) -> None:
        SqliteDatabase(self.connection, MIGRATIONS[:1]).initialize()
        self.connection.execute(
            "INSERT INTO devices (code, name, line, enabled) VALUES (?, ?, ?, ?)",
            ("SMT-01", "Machine 1", "Line A", 1),
        )
        self.connection.commit()

        SqliteDatabase(self.connection).initialize()

        self.assertEqual(
            ("SMT-01", "Machine 1", 0),
            self.connection.execute(
                "SELECT code, name, archived FROM devices WHERE code = 'SMT-01'"
            ).fetchone(),
        )
        self.assertEqual(4, self.connection.execute("PRAGMA user_version").fetchone()[0])

    def test_repairs_lagging_user_version_after_validating_complete_history(self) -> None:
        database = SqliteDatabase(self.connection)
        database.initialize()
        self.connection.execute(
            "INSERT INTO devices (code, name, line, enabled) VALUES (?, ?, ?, ?)",
            ("SMT-01", "Machine 1", "Line A", 1),
        )
        self.connection.execute("PRAGMA user_version = 1")
        self.connection.commit()

        database.initialize()

        self.assertEqual(4, self.connection.execute("PRAGMA user_version").fetchone()[0])
        self.assertEqual(
            ("SMT-01", "Machine 1"),
            self.connection.execute(
                "SELECT code, name FROM devices WHERE code = 'SMT-01'"
            ).fetchone(),
        )

    def test_does_not_repair_user_version_when_history_checksum_is_invalid(self) -> None:
        database = SqliteDatabase(self.connection)
        database.initialize()
        self.connection.execute("PRAGMA user_version = 1")
        self.connection.execute(
            "UPDATE schema_migrations SET checksum = 'tampered' WHERE version = 2"
        )
        self.connection.commit()

        with self.assertRaisesRegex(MigrationError, "modified after application"):
            database.initialize()

        self.assertEqual(1, self.connection.execute("PRAGMA user_version").fetchone()[0])

    def test_rejects_user_version_ahead_of_valid_history(self) -> None:
        SqliteDatabase(self.connection, MIGRATIONS[:1]).initialize()
        self.connection.execute("PRAGMA user_version = 2")
        self.connection.commit()

        with self.assertRaisesRegex(MigrationError, "does not match migration history"):
            SqliteDatabase(self.connection).initialize()

    def test_failed_migration_rolls_back_version_and_history(self) -> None:
        SqliteDatabase(self.connection).initialize()
        broken = Migration(
            5,
            "broken_test_migration",
            "CREATE TABLE should_rollback (id INTEGER); INVALID SQL;",
            irreversible_reason="Test-only failure",
        )

        with self.assertRaises(MigrationError):
            SqliteDatabase(self.connection, (*MIGRATIONS, broken)).initialize()

        tables = {
            row[0]
            for row in self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        self.assertNotIn("should_rollback", tables)
        self.assertEqual(4, self.connection.execute("PRAGMA user_version").fetchone()[0])
        self.assertEqual(
            [(1,), (2,), (3,), (4,)],
            self.connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            ).fetchall(),
        )

    def test_duplicate_legacy_station_codes_roll_back_global_unique_migration(self) -> None:
        SqliteDatabase(self.connection, MIGRATIONS[:2]).initialize()
        self.connection.executemany(
            "INSERT INTO devices (code, name, line, enabled) VALUES (?, ?, ?, ?)",
            [
                ("SMT-01", "Machine 1", "Line A", 1),
                ("SMT-02", "Machine 2", "Line A", 1),
            ],
        )
        self.connection.executemany(
            "INSERT INTO stations (device_code, code, enabled, referenced) "
            "VALUES (?, ?, ?, ?)",
            [
                ("SMT-01", "F-01", 1, 0),
                ("SMT-02", "F-01", 1, 0),
            ],
        )
        self.connection.commit()

        with self.assertRaisesRegex(MigrationError, "globally_unique_station_codes"):
            SqliteDatabase(self.connection).initialize()

        self.assertEqual(2, self.connection.execute("PRAGMA user_version").fetchone()[0])
        self.assertEqual(
            2,
            self.connection.execute(
                "SELECT COUNT(*) FROM stations WHERE code = 'F-01'"
            ).fetchone()[0],
        )

    def test_rejects_database_newer_than_application(self) -> None:
        self.connection.execute("PRAGMA user_version = 99")

        with self.assertRaises(MigrationError):
            SqliteDatabase(self.connection).initialize()


if __name__ == "__main__":
    unittest.main()
