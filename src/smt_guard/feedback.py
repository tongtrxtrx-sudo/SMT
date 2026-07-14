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


class VoicePrompt(Enum):
    """Fixed Chinese announcements for safety-critical operator actions."""

    OPERATOR_CONFIRMED = "操作员已确认"
    BOM_IMPORTED = "BOM 导入成功"
    CONFIGURATION_IMPORTED = "站位配置导入成功"
    IMPORT_FAILED = "导入失败，请查看屏幕提示"
    BOM_PUBLISHED = "BOM 已发布"
    BOM_ACTIVATED = "BOM 已启用"
    BOM_OBSOLETED = "BOM 已作废"
    BOM_ARCHIVED = "BOM 已归档"
    CONFIGURATION_PUBLISHED = "产品配置已发布"
    CONFIGURATION_ACTIVATED = "产品配置已启用"
    CONFIGURATION_DISABLED = "产品配置已停用"
    CONFIGURATION_ARCHIVED = "产品配置已归档"
    LIFECYCLE_FAILED = "状态操作失败，请查看屏幕提示"
    RUN_STARTED = "生产运行已开始，请扫描设备码"
    RUN_REPLACED = "原生产运行已中断，新生产运行已开始"
    RUN_INTERRUPTED = "生产运行已中断"
    RUN_RESUMED = "生产运行已恢复，请继续扫码"
    SCAN_REJECTED = "扫码无效，请按屏幕提示重新扫描"
    MATERIAL_OK = "对料正确"
    MATERIAL_NG = "对料错误，请检查物料"
    RUN_COMPLETED = "全部对料完成"
    RECORDS_EXPORTED = "扫码记录导出成功"
    EXPORT_FAILED = "扫码记录导出失败，请查看屏幕提示"


class AnnouncementSink(Protocol):
    """Boundary for non-blocking spoken operator announcements."""

    def announce(self, prompt: VoicePrompt) -> None:
        """Speak one fixed operator prompt."""


class SilentAnnouncementSink:
    """No-op announcer used by tests, smoke checks, and unavailable engines."""

    def announce(self, prompt: VoicePrompt) -> None:
        del prompt


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
