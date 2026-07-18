"""Current operator session shared by application workflows."""

from dataclasses import dataclass
from pathlib import Path


class LastOperatorStore:
    """Persist the last confirmed operator beside the local application database."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> str:
        """Return the last operator, or an empty value when no preference exists."""
        try:
            return self._path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            return ""
        except OSError:
            return ""

    def save(self, operator: str) -> None:
        """Atomically replace the preference after a successful confirmation."""
        normalized = operator.strip()
        if not normalized:
            raise ValueError("操作员不能为空")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(f"{self._path.suffix}.tmp")
        temporary.write_text(normalized, encoding="utf-8")
        temporary.replace(self._path)


@dataclass
class OperatorSession:
    """Hold the signed-in operator for the lifetime of one application process."""

    operator: str = ""

    def __post_init__(self) -> None:
        self.operator = self.operator.strip()

    def sign_in(self, operator: str) -> str:
        """Set and return a non-empty operator identifier."""
        normalized = operator.strip()
        if not normalized:
            raise ValueError("操作员不能为空")
        self.operator = normalized
        return normalized

    def require(self) -> str:
        """Return the active operator or reject an unauthenticated operation."""
        if not self.operator:
            raise ValueError("请先录入当前操作员")
        return self.operator
