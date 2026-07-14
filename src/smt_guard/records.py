"""Append-only verification attempt records."""

from dataclasses import dataclass, replace
from datetime import datetime

from smt_guard.verification import VerificationResult


@dataclass(frozen=True)
class Attempt:
    """One immutable material verification attempt."""

    id: int | None
    timestamp: datetime
    run_id: str
    product_code: str
    product_version: str
    device_code: str
    station_code: str
    expected_material: str
    scanned_material: str
    result: VerificationResult
    repeated: bool


class InMemoryAttemptRepository:
    """Safe in-memory repository used by core logic and tests."""

    def __init__(self) -> None:
        self._records: list[Attempt] = []
        self._next_id = 1

    def append(self, attempt: Attempt) -> Attempt:
        stored = replace(attempt, id=self._allocate_id())
        self._records.append(stored)
        return stored

    def list_for_run(self, run_id: str) -> list[Attempt]:
        return [record for record in self._records if record.run_id == run_id]

    def _allocate_id(self) -> int:
        allocated = self._next_id
        self._next_id += 1
        return allocated
