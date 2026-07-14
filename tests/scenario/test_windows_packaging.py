import os
import tomllib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from smt_guard.app import main
from smt_guard.platform import default_data_dir


class WindowsPackagingTests(unittest.TestCase):
    app: QApplication

    @classmethod
    def setUpClass(cls) -> None:
        application = QApplication.instance()
        if application is None:
            cls.app = QApplication([])
        elif isinstance(application, QApplication):
            cls.app = application
        else:
            raise RuntimeError("A non-GUI Qt application already exists")

    def setUp(self) -> None:
        self.project_root = Path(__file__).resolve().parents[2]

    def test_declares_reproducible_windowed_one_folder_build(self) -> None:
        with (self.project_root / "pyproject.toml").open("rb") as stream:
            project = tomllib.load(stream)
        spec = (self.project_root / "packaging" / "SMTGuard.spec").read_text("utf-8")
        script = (self.project_root / "scripts" / "build_windows.ps1").read_text("utf-8")

        self.assertTrue(
            any(item.startswith("pyinstaller") for item in project["dependency-groups"]["dev"])
        )
        self.assertIn('name="SMTGuard"', spec)
        self.assertIn("console=False", spec)
        self.assertIn("src/smt_guard/__main__.py", spec)
        self.assertIn("packaging/SMTGuard.spec", script.replace("\\", "/"))

    def test_smoke_mode_uses_isolated_data_and_never_shows_window(self) -> None:
        with TemporaryDirectory() as directory:
            exit_code = main(
                ["--smoke-test"],
                environ={"SMT_GUARD_DATA_DIR": directory},
            )
            database = Path(directory) / "smt_guard.sqlite3"

            self.assertEqual(0, exit_code)
            self.assertTrue(database.is_file())
            self.assertFalse(any(widget.isVisible() for widget in self.app.topLevelWidgets()))

    def test_data_directory_honors_explicit_override(self) -> None:
        path = default_data_dir(
            environ={"SMT_GUARD_DATA_DIR": "D:/SMT-Test-Data"},
            home=Path("C:/Users/Operator"),
        )

        self.assertEqual(Path("D:/SMT-Test-Data"), path)

    def test_readme_documents_build_and_packaged_smoke_test(self) -> None:
        readme = (self.project_root / "README.md").read_text("utf-8")

        self.assertIn("build_windows.ps1", readme)
        self.assertIn("SMTGuard.exe --smoke-test", readme)


if __name__ == "__main__":
    unittest.main()
