"""Append-only audit domain records."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class AuditEntry:
    """One immutable critical-change audit event."""

    id: int
    timestamp: datetime
    actor: str
    action: str
    entity_type: str
    entity_key: str
    before_json: str | None
    after_json: str | None
