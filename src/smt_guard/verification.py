"""Exact material-code verification rules."""

from enum import Enum


def normalize_material_code(value: str) -> str:
    """Normalize scanner framing without changing material-code semantics."""
    return value.strip()


class VerificationResult(Enum):
    """Possible material verification results."""

    OK = "OK"
    NG = "NG"


class MaterialVerifier:
    """Compare material codes without fuzzy matching or case conversion."""

    def verify(self, expected: str, scanned: str) -> VerificationResult:
        """Return OK only when trimmed material codes are exactly equal."""
        if normalize_material_code(expected) == normalize_material_code(scanned):
            return VerificationResult.OK
        return VerificationResult.NG
