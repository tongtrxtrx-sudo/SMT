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
             "run_station_states", "audit_logs"} <= tables
        )
        applied = self.connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()
        self.assertEqual([(1,), (2,)], applied)
        self.assertEqual(2, self.connection.execute("PRAGMA user_version").fetchone()[0])
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

    def test_station_requires_an_existing_device(self) -> None:
        SqliteDatabase(self.connection).initialize()

        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO stations (device_code, code, enabled, referenced) "
                "VALUES (?, ?, ?, ?)",
                ("SMT-99", "F-01", 1, 0),
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
        self.assertEqual(2, self.connection.execute("PRAGMA user_version").fetchone()[0])

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

        self.assertEqual(2, self.connection.execute("PRAGMA user_version").fetchone()[0])
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
            3,
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
        self.assertEqual(2, self.connection.execute("PRAGMA user_version").fetchone()[0])
        self.assertEqual(
            [(1,), (2,)],
            self.connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            ).fetchall(),
        )

    def test_rejects_database_newer_than_application(self) -> None:
        self.connection.execute("PRAGMA user_version = 99")

        with self.assertRaises(MigrationError):
            SqliteDatabase(self.connection).initialize()


if __name__ == "__main__":
    unittest.main()
