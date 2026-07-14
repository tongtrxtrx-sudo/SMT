"""Current operator session shared by application workflows."""

from dataclasses import dataclass


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
