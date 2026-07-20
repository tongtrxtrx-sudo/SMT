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

    def device_for_station(self, station_code: str) -> str | None:
        """Resolve the owning device for a globally unique configured station."""
        normalized = station_code.strip()
        matches = [device for device, station in self.assignments if station == normalized]
        if len(matches) > 1:
            raise ValueError(f"Station code is not globally unique: {normalized}")
        return matches[0] if matches else None


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
    """Process globally unique station and material scans in a strict sequence."""

    def __init__(
        self,
        configuration: ProductConfiguration,
        verifier: MaterialVerifier | None = None,
    ) -> None:
        self._configuration = configuration
        self._verifier = verifier or MaterialVerifier()
        self._step = ScanStep.STATION
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

    def reset_station(self) -> None:
        """Discard the selected station and explicitly return to station scanning."""
        self._device = None
        self._station = None
        self._step = ScanStep.STATION

    def handle_scan(self, raw_code: str) -> ScanOutcome:
        code = normalize_material_code(raw_code)
        if self._step is ScanStep.STATION:
            return self._handle_station(code)
        return self._handle_material(code)

    def _handle_station(self, code: str) -> ScanOutcome:
        device = self._configuration.device_for_station(code)
        if device is None:
            return self._rejected(ScanStep.STATION, "Unknown station")
        self._device = device
        self._station = code
        self._step = ScanStep.MATERIAL
        return ScanOutcome(True, self._step)

    def _handle_material(self, code: str) -> ScanOutcome:
        if self._device is None or self._station is None:
            self._step = ScanStep.STATION
            return self._rejected(self._step, "Station is required")
        expected = self._configuration.required_material(self._device, self._station)
        result = self._verifier.verify(expected, code)
        if result is VerificationResult.OK:
            self._device = None
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
