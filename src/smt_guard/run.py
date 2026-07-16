"""Application service for one material-verification run."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol

from smt_guard.feedback import AudioSink, FeedbackController, FeedbackState
from smt_guard.records import Attempt
from smt_guard.scan import ProductConfiguration, ScanOutcome, ScanSession, ScanStep
from smt_guard.verification import VerificationResult


class AttemptSink(Protocol):
    """Append-only persistence boundary used by a verification run."""

    def append(self, attempt: Attempt) -> Attempt:
        """Store one immutable material attempt."""
        ...


class RunStatus(Enum):
    """Persistent lifecycle state of a production verification run."""

    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    INTERRUPTED = "INTERRUPTED"


@dataclass(frozen=True)
class ProductionRun:
    """Persisted run header, configuration snapshot, and progress summary."""

    run_id: str
    configuration: ProductConfiguration
    operator: str
    status: RunStatus
    started_at: datetime
    completed_stations: int
    total_stations: int
    completed_at: datetime | None = None
    interrupted_at: datetime | None = None
    interruption_reason: str = ""


@dataclass(frozen=True)
class RunStationState:
    """Read-only state of one station in a persisted run snapshot."""

    device_code: str
    station_code: str
    expected_material: str
    completed: bool
    completed_at: datetime | None = None


class RunPersistence(Protocol):
    """Atomic production-run persistence used by the application service."""

    def start(
        self,
        run_id: str,
        configuration: ProductConfiguration,
        *,
        operator: str,
        started_at: datetime,
    ) -> ProductionRun:
        """Persist a run before any scans are recorded."""
        ...

    def record_attempt(self, attempt: Attempt) -> Attempt:
        """Append an attempt and update station/run state in one transaction."""
        ...

    def interrupt(
        self,
        run_id: str,
        *,
        operator: str,
        interrupted_at: datetime,
        reason: str,
    ) -> None:
        """Persist an operator interruption."""
        ...


@dataclass(frozen=True)
class RunUpdate:
    """One scan outcome with operator feedback and optional stored attempt."""

    outcome: ScanOutcome
    feedback: FeedbackState
    attempt: Attempt | None = None


class VerificationRun:
    """Coordinate ordered scans, progress feedback, and attempt history."""

    def __init__(
        self,
        run_id: str,
        configuration: ProductConfiguration,
        attempts: AttemptSink,
        audio: AudioSink,
        *,
        clock: Callable[[], datetime],
        runs: RunPersistence | None = None,
        operator: str = "SYSTEM",
        start_persisted_run: bool = True,
        completed_stations: set[tuple[str, str]] | None = None,
    ) -> None:
        self.run_id = run_id.strip()
        self.configuration = configuration
        self._attempts = attempts
        self._clock = clock
        self._runs = runs
        self._operator = operator.strip() or "SYSTEM"
        self._session = ScanSession(configuration)
        self._completed: set[tuple[str, str]] = (
            set() if completed_stations is None else set(completed_stations)
        )
        self._feedback = FeedbackController(
            len(configuration.assignments),
            audio,
            completed_stations=len(self._completed),
        )
        if self._runs is not None and start_persisted_run:
            self._runs.start(
                self.run_id,
                configuration,
                operator=self._operator,
                started_at=self._clock(),
            )

    @classmethod
    def resume(
        cls,
        persisted: ProductionRun,
        attempts: AttemptSink,
        audio: AudioSink,
        *,
        clock: Callable[[], datetime],
        runs: RunPersistence,
        completed_stations: set[tuple[str, str]],
        operator: str | None = None,
    ) -> "VerificationRun":
        """Rehydrate an already-persisted running snapshot without creating a new run."""
        if persisted.status is not RunStatus.RUNNING:
            raise ValueError(f"Production run is not running: {persisted.run_id}")
        return cls(
            persisted.run_id,
            persisted.configuration,
            attempts,
            audio,
            clock=clock,
            runs=runs,
            operator=persisted.operator if operator is None else operator,
            start_persisted_run=False,
            completed_stations=completed_stations,
        )

    @property
    def initial_feedback(self) -> FeedbackState:
        """Return the first operator prompt for a new run."""
        return self._feedback.waiting(self._session.current_step)

    @property
    def current_step(self) -> ScanStep:
        """Expose the current safe scanner step to presentation adapters."""
        return self._session.current_step

    @property
    def completed(self) -> bool:
        """Return whether every station in the immutable snapshot is complete."""
        return len(self._completed) == len(self.configuration.assignments)

    def handle_scan(self, raw_code: str) -> RunUpdate:
        session_state = self._session.snapshot()
        device = self._session.current_device
        station = self._session.current_station
        outcome = self._session.handle_scan(raw_code)
        if not outcome.accepted or outcome.verification is None:
            return RunUpdate(outcome, self._feedback.waiting(outcome.next_step))

        if device is None or station is None:
            raise RuntimeError("Material verification completed without device and station")
        if outcome.expected_material is None or outcome.scanned_material is None:
            raise RuntimeError("Material verification did not include material codes")

        station_key = (device, station)
        repeated = station_key in self._completed
        newly_completed = outcome.verification is VerificationResult.OK and not repeated
        pending_attempt = Attempt(
            id=None,
            timestamp=self._clock(),
            run_id=self.run_id,
            product_code=self.configuration.product_code,
            product_version=self.configuration.version,
            device_code=device,
            station_code=station,
            expected_material=outcome.expected_material,
            scanned_material=outcome.scanned_material,
            result=outcome.verification,
            repeated=repeated,
        )
        try:
            attempt = (
                self._runs.record_attempt(pending_attempt)
                if self._runs is not None
                else self._attempts.append(pending_attempt)
            )
        except Exception:
            self._session.restore(session_state)
            raise
        if newly_completed:
            self._completed.add(station_key)
        feedback = self._feedback.verified(
            outcome.expected_material,
            outcome.scanned_material,
            outcome.verification,
            station_newly_completed=newly_completed,
        )
        return RunUpdate(outcome, feedback, attempt)

    def interrupt(self, reason: str) -> None:
        """Persist an interrupted run, including runs with no scan attempts."""
        if self._runs is None:
            return
        self._runs.interrupt(
            self.run_id,
            operator=self._operator,
            interrupted_at=self._clock(),
            reason=reason.strip(),
        )
