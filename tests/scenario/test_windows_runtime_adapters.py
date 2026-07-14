import tomllib
import unittest
from datetime import UTC, datetime
from pathlib import Path

from smt_guard.feedback import FeedbackTone
from smt_guard.platform import RunIdGenerator, WindowsAudioSink, default_data_dir


class WindowsRuntimeAdapterTests(unittest.TestCase):
    def test_resolves_local_app_data_and_home_fallback(self) -> None:
        local = default_data_dir(
            environ={"LOCALAPPDATA": "C:/Users/Operator/AppData/Local"},
            home=Path("C:/Users/Operator"),
        )
        fallback = default_data_dir(environ={}, home=Path("C:/Users/Operator"))

        self.assertEqual(Path("C:/Users/Operator/AppData/Local/SMTGuard"), local)
        self.assertEqual(Path("C:/Users/Operator/AppData/Local/SMTGuard"), fallback)

    def test_generates_readable_unique_run_identifiers(self) -> None:
        tokens = iter(("ab-cd_1234", "efgh5678"))
        generator = RunIdGenerator(
            clock=lambda: datetime(2026, 7, 11, 12, 15, 30, tzinfo=UTC),
            token_factory=lambda: next(tokens),
        )

        first = generator()
        second = generator()

        self.assertEqual("RUN-20260711-121530-ABCD1234", first)
        self.assertEqual("RUN-20260711-121530-EFGH5678", second)
        self.assertNotEqual(first, second)

    def test_maps_feedback_tones_to_windows_beep_kinds(self) -> None:
        beep_kinds: list[int] = []
        audio = WindowsAudioSink(beeper=lambda kind: beep_kinds.append(kind))

        audio.emit(FeedbackTone.OK)
        audio.emit(FeedbackTone.NG)

        self.assertEqual([WindowsAudioSink.OK_BEEP, WindowsAudioSink.NG_BEEP], beep_kinds)
        self.assertNotEqual(WindowsAudioSink.OK_BEEP, WindowsAudioSink.NG_BEEP)

    def test_declares_project_script_entry_point(self) -> None:
        project_root = Path(__file__).resolve().parents[2]
        with (project_root / "pyproject.toml").open("rb") as stream:
            project = tomllib.load(stream)

        self.assertEqual("smt_guard.app:main", project["project"]["scripts"]["smt-guard"])


if __name__ == "__main__":
    unittest.main()
