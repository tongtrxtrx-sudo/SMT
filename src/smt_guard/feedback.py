"""UI-independent operator feedback state."""

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from smt_guard.scan import ScanStep
from smt_guard.verification import VerificationResult


class FeedbackTone(Enum):
    """Abstract tones emitted at the audio boundary."""

    OK = "OK"
    NG = "NG"


class VisualIntent(Enum):
    """Color intent consumed by the GUI layer."""

    NEUTRAL = "NEUTRAL"
    OK = "OK"
    NG = "NG"


class AudioSink(Protocol):
    """Boundary used by the GUI adapter to play feedback."""

    def emit(self, tone: FeedbackTone) -> None:
        """Emit one abstract feedback tone."""


@dataclass(frozen=True)
class FeedbackState:
    """All feedback data required by the operator screen."""

    message: str
    intent: VisualIntent
    expected_material: str = ""
    scanned_material: str = ""
    completed_stations: int = 0
    total_stations: int = 0
    complete: bool = False


class FeedbackController:
    """Build deterministic feedback without depending on GUI widgets."""

    WAITING_MESSAGES = {
        ScanStep.DEVICE: "请扫描设备码",
        ScanStep.STATION: "请扫描站位码",
        ScanStep.MATERIAL: "请扫描物料码",
    }

    def __init__(
        self,
        total_stations: int,
        audio: AudioSink,
        *,
        completed_stations: int = 0,
    ) -> None:
        self._total = total_stations
        self._completed = completed_stations
        self._audio = audio

    def waiting(self, step: ScanStep) -> FeedbackState:
        return self._state(
            message=self.WAITING_MESSAGES[step],
            intent=VisualIntent.NEUTRAL,
        )

    def verified(
        self,
        expected: str,
        scanned: str,
        result: VerificationResult,
        *,
        station_newly_completed: bool,
    ) -> FeedbackState:
        if result is VerificationResult.OK:
            if station_newly_completed:
                self._completed += 1
            self._audio.emit(FeedbackTone.OK)
            complete = self._completed >= self._total
            message = "全部对料完成" if complete else "对料正确"
            intent = VisualIntent.OK
        else:
            self._audio.emit(FeedbackTone.NG)
            complete = False
            message = "对料错误"
            intent = VisualIntent.NG

        return self._state(
            message=message,
            intent=intent,
            expected_material=expected,
            scanned_material=scanned,
            complete=complete,
        )

    def _state(
        self,
        *,
        message: str,
        intent: VisualIntent,
        expected_material: str = "",
        scanned_material: str = "",
        complete: bool | None = None,
    ) -> FeedbackState:
        return FeedbackState(
            message=message,
            intent=intent,
            expected_material=expected_material,
            scanned_material=scanned_material,
            completed_stations=self._completed,
            total_stations=self._total,
            complete=self._completed >= self._total if complete is None else complete,
        )
