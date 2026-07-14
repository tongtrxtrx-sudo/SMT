"""Ordered scanner-input state machine."""

from dataclasses import dataclass
from enum import Enum

from smt_guard.verification import (
    MaterialVerifier,
    VerificationResult,
    normalize_material_code,
)


class ScanStep(Enum):
    """Expected type of the next scanner input."""

    DEVICE = "DEVICE"
    STATION = "STATION"
    MATERIAL = "MATERIAL"


@dataclass(frozen=True)
class ProductConfiguration:
    """Versioned station-to-material assignments for one product."""

    product_code: str
    version: str
    assignments: dict[tuple[str, str], str]
    bom_version_id: int | None = None

    def required_material(self, device_code: str, station_code: str) -> str:
        """Return the material required at one configured station."""
        return self.assignments[(device_code.strip(), station_code.strip())]

    def contains_device(self, device_code: str) -> bool:
        normalized = device_code.strip()
        return any(device == normalized for device, _ in self.assignments)

    def contains_station(self, device_code: str, station_code: str) -> bool:
        return (device_code.strip(), station_code.strip()) in self.assignments


@dataclass(frozen=True)
class ScanOutcome:
    """Result of processing one scanner input."""

    accepted: bool
    next_step: ScanStep
    reason: str = ""
    verification: VerificationResult | None = None
    expected_material: str | None = None
    scanned_material: str | None = None


class ScanSession:
    """Process device, station, and material scans in a strict sequence."""

    def __init__(
        self,
        configuration: ProductConfiguration,
        verifier: MaterialVerifier | None = None,
    ) -> None:
        self._configuration = configuration
        self._verifier = verifier or MaterialVerifier()
        self._step = ScanStep.DEVICE
        self._device: str | None = None
        self._station: str | None = None

    @property
    def current_step(self) -> ScanStep:
        """Return the input type currently expected by the session."""
        return self._step

    @property
    def current_device(self) -> str | None:
        """Return the accepted device for the current scan sequence."""
        return self._device

    @property
    def current_station(self) -> str | None:
        """Return the accepted station while waiting for material."""
        return self._station

    def snapshot(self) -> tuple[ScanStep, str | None, str | None]:
        """Capture mutable scanner state before an external write boundary."""
        return self._step, self._device, self._station

    def restore(self, state: tuple[ScanStep, str | None, str | None]) -> None:
        """Restore scanner state when a material attempt cannot be persisted."""
        self._step, self._device, self._station = state

    def handle_scan(self, raw_code: str) -> ScanOutcome:
        code = normalize_material_code(raw_code)
        if self._step is ScanStep.DEVICE:
            return self._handle_device(code)
        if self._step is ScanStep.STATION:
            return self._handle_station(code)
        return self._handle_material(code)

    def _handle_device(self, code: str) -> ScanOutcome:
        if not self._configuration.contains_device(code):
            return self._rejected(ScanStep.DEVICE, "Unknown device")
        self._device = code
        self._step = ScanStep.STATION
        return ScanOutcome(True, self._step)

    def _handle_station(self, code: str) -> ScanOutcome:
        if self._device is not None and self._configuration.contains_station(self._device, code):
            self._station = code
            self._step = ScanStep.MATERIAL
            return ScanOutcome(True, self._step)
        if self._configuration.contains_device(code):
            self._device = code
            self._station = None
            self._step = ScanStep.STATION
            return ScanOutcome(True, self._step)
        if self._device is None:
            return self._rejected(ScanStep.STATION, "Unknown station for selected device")
        return self._rejected(ScanStep.STATION, "Unknown station for selected device")

    def _handle_material(self, code: str) -> ScanOutcome:
        if self._device is None or self._station is None:
            self._step = ScanStep.DEVICE
            return self._rejected(self._step, "Device and station are required")
        expected = self._configuration.required_material(self._device, self._station)
        result = self._verifier.verify(expected, code)
        if result is VerificationResult.OK:
            self._station = None
            self._step = ScanStep.STATION
        return ScanOutcome(
            True,
            self._step,
            verification=result,
            expected_material=expected,
            scanned_material=code,
        )

    @staticmethod
    def _rejected(step: ScanStep, reason: str) -> ScanOutcome:
        return ScanOutcome(False, step, reason)
