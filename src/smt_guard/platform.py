"""Windows runtime adapters for local storage, run IDs, and feedback audio."""

import os
from collections.abc import Callable, Mapping
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from smt_guard.feedback import FeedbackTone, VoicePrompt


def default_data_dir(
    *,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    """Return the per-user Windows application data directory."""
    environment = os.environ if environ is None else environ
    home_directory = Path.home() if home is None else home
    explicit_directory = environment.get("SMT_GUARD_DATA_DIR")
    if explicit_directory:
        return Path(explicit_directory)
    local_app_data = environment.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else home_directory / "AppData" / "Local"
    return base / "SMTGuard"


def _random_token() -> str:
    return uuid4().hex


class RunIdGenerator:
    """Generate readable run identifiers with timestamp and random token."""

    def __init__(
        self,
        *,
        clock: Callable[[], datetime],
        token_factory: Callable[[], str] = _random_token,
    ) -> None:
        self._clock = clock
        self._token_factory = token_factory

    def __call__(self) -> str:
        timestamp = self._clock().strftime("%Y%m%d-%H%M%S")
        token = "".join(character for character in self._token_factory() if character.isalnum())
        if len(token) < 8:
            raise ValueError("Run identifier token must contain at least eight letters or digits")
        return f"RUN-{timestamp}-{token[:8].upper()}"


def _message_beep(kind: int) -> object:
    import winsound

    return winsound.MessageBeep(kind)


class WindowsAudioSink:
    """Emit abstract operator feedback through Windows system sounds."""

    OK_BEEP = 0x00000000
    NG_BEEP = 0x00000010

    def __init__(self, beeper: Callable[[int], object] = _message_beep) -> None:
        self._beeper = beeper

    def emit(self, tone: FeedbackTone) -> None:
        kind = self.OK_BEEP if tone is FeedbackTone.OK else self.NG_BEEP
        self._beeper(kind)


class WindowsSpeechSink:
    """Speak fixed Chinese prompts through a non-blocking Qt speech engine."""

    def __init__(
        self,
        speaker: Callable[[str], object],
        *,
        stopper: Callable[[], object] | None = None,
        engine_owner: object | None = None,
    ) -> None:
        self._speaker = speaker
        self._stopper = stopper
        self._engine_owner = engine_owner

    def announce(self, prompt: VoicePrompt) -> None:
        if self._stopper is not None:
            with suppress(Exception):
                self._stopper()
        with suppress(Exception):
            self._speaker(prompt.value)
