from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QLocale
from PySide6.QtWidgets import QApplication

from smt_guard.app import (
    _create_windows_announcer,  # pyright: ignore[reportPrivateUsage]
    _voice_announcements_enabled,  # pyright: ignore[reportPrivateUsage]
)
from smt_guard.feedback import SilentAnnouncementSink, VoicePrompt
from smt_guard.platform import WindowsSpeechSink


class FakeVoice:
    def __init__(self, locale: str) -> None:
        self._locale = QLocale(locale)

    def locale(self) -> QLocale:
        return self._locale


class FakeSpeechEngine:
    available = ["mock", "winrt", "sapi"]
    voice_locales: dict[str, list[str]] = {
        "mock": ["en_GB"],
        "winrt": ["zh_CN"],
        "sapi": ["zh_CN"],
    }
    created: list[FakeSpeechEngine] = []

    def __init__(self, name: str) -> None:
        self.name = name
        self.locale = QLocale()
        self.voice: FakeVoice | None = None
        self.rate = 0.0
        self.volume = 0.0
        self.spoken: list[str] = []
        self.stops = 0
        self.created.append(self)

    @classmethod
    def availableEngines(cls) -> list[str]:
        return cls.available

    def setLocale(self, locale: QLocale) -> None:
        self.locale = locale

    def availableVoices(self) -> list[FakeVoice]:
        return [FakeVoice(locale) for locale in self.voice_locales.get(self.name, [])]

    def setVoice(self, voice: FakeVoice) -> None:
        self.voice = voice

    def setRate(self, rate: float) -> None:
        self.rate = rate

    def setVolume(self, volume: float) -> None:
        self.volume = volume

    def stop(self) -> None:
        self.stops += 1

    def say(self, text: str) -> None:
        self.spoken.append(text)


class VoiceAnnouncementTests(unittest.TestCase):
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
        FakeSpeechEngine.available = ["mock", "winrt", "sapi"]
        FakeSpeechEngine.voice_locales = {
            "mock": ["en_GB"],
            "winrt": ["zh_CN"],
            "sapi": ["zh_CN"],
        }
        FakeSpeechEngine.created = []

    def test_prompt_catalog_contains_only_fixed_operator_phrases(self) -> None:
        self.assertEqual(23, len(VoicePrompt))
        for prompt in VoicePrompt:
            with self.subTest(prompt=prompt.name):
                self.assertTrue(prompt.value)
                self.assertNotIn("{", prompt.value)
                self.assertNotIn("}", prompt.value)

    def test_voice_is_enabled_by_default_and_accepts_explicit_off_values(self) -> None:
        self.assertTrue(_voice_announcements_enabled({}))
        self.assertTrue(_voice_announcements_enabled({"SMT_GUARD_VOICE_ENABLED": "yes"}))
        for value in ("0", "false", "NO", " off "):
            with self.subTest(value=value):
                self.assertFalse(
                    _voice_announcements_enabled({"SMT_GUARD_VOICE_ENABLED": value})
                )

    def test_factory_prefers_sapi_when_it_has_a_chinese_voice(self) -> None:
        with patch("smt_guard.app.QTextToSpeech", FakeSpeechEngine):
            announcer = _create_windows_announcer()

        self.assertIsInstance(announcer, WindowsSpeechSink)
        self.assertEqual(["sapi"], [engine.name for engine in FakeSpeechEngine.created])
        engine = FakeSpeechEngine.created[0]
        self.assertEqual("zh_CN", engine.locale.name())
        self.assertIsNotNone(engine.voice)
        self.assertEqual(-0.1, engine.rate)
        self.assertEqual(1.0, engine.volume)

    def test_factory_tries_winrt_when_sapi_has_no_chinese_voice(self) -> None:
        FakeSpeechEngine.voice_locales["sapi"] = ["en_US"]

        with patch("smt_guard.app.QTextToSpeech", FakeSpeechEngine):
            announcer = _create_windows_announcer()

        self.assertIsInstance(announcer, WindowsSpeechSink)
        self.assertEqual(["sapi", "winrt"], [engine.name for engine in FakeSpeechEngine.created])

    def test_factory_safely_falls_back_when_no_chinese_voice_exists(self) -> None:
        FakeSpeechEngine.voice_locales = {"mock": ["en_GB"], "winrt": [], "sapi": ["en_US"]}

        with patch("smt_guard.app.QTextToSpeech", FakeSpeechEngine):
            announcer = _create_windows_announcer()

        self.assertIsInstance(announcer, SilentAnnouncementSink)


if __name__ == "__main__":
    unittest.main()
