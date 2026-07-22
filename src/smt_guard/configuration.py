"""Cross-validation and creation of product station configurations."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol

from smt_guard.master_data import Station, UnknownEntityError
from smt_guard.scan import ProductConfiguration


class ImportValidationError(ValueError):
    """Raised when imported station assignments are not safe to activate."""


class ConfigurationStatus(Enum):
    """Lifecycle of a versioned product station configuration."""

    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    ARCHIVED = "ARCHIVED"


@dataclass(frozen=True)
class ProductConfigurationRecord:
    """Persisted configuration plus immutable lifecycle metadata."""

    configuration: ProductConfiguration
    status: ConfigurationStatus
    created_at: datetime
    created_by: str
    published_at: datetime | None = None
    activated_at: datetime | None = None


class MasterDataLookup(Protocol):
    """Master-data operations required while building a configuration."""

    def is_device_enabled(self, code: str) -> bool:
        """Return whether a device exists and is enabled."""
        ...

    def is_station_enabled(self, device_code: str, station_code: str) -> bool:
        """Return whether a station exists and is enabled."""
        ...

    def resolve_station(self, station_code: str) -> Station:
        """Resolve one globally unique station code to its owning device."""
        ...


class ProductConfigurationBuilder:
    """Validate station/material rows against physical master data."""

    REQUIRED_COLUMNS = ("站位编码", "物料编码")

    def __init__(self, master_data: MasterDataLookup) -> None:
        self._master_data = master_data

    def build(
        self,
        product_code: str,
        version: str,
        materials: Mapping[str, object],
        station_rows: Sequence[Mapping[str, object]],
    ) -> ProductConfiguration:
        del materials  # Kept in the signature for legacy integrations.
        assignments: dict[tuple[str, str], str] = {}
        errors: list[str] = []

        for index, row in enumerate(station_rows, start=2):
            row_number = self._row_number(row, index)
            missing = [column for column in self.REQUIRED_COLUMNS if column not in row]
            if missing:
                errors.append(f"Row {row_number}: missing column {missing[0]}")
                continue

            supplied_device, station, material = self._codes(row)
            if not station or not material:
                errors.append(f"Row {row_number}: station and material are required")
                continue
            try:
                resolved = self._master_data.resolve_station(station)
            except UnknownEntityError:
                errors.append(f"Row {row_number}: unknown station {station}")
                continue
            device = resolved.device_code
            if supplied_device and supplied_device != device:
                errors.append(
                    f"Row {row_number}: station {station} belongs to device {device}, "
                    f"not {supplied_device}"
                )
                continue
            if not self._master_data.is_device_enabled(device):
                errors.append(f"Row {row_number}: unknown or disabled device {device}")
                continue
            if not self._master_data.is_station_enabled(device, station):
                errors.append(f"Row {row_number}: unknown or disabled station {device}/{station}")
                continue
            key = (device, station)
            if key in assignments:
                errors.append(f"Row {row_number}: duplicate station {device}/{station}")
                continue
            assignments[key] = material

        if errors:
            raise ImportValidationError("; ".join(errors))
        if not assignments:
            raise ImportValidationError("Station table must contain at least one assignment")
        return ProductConfiguration(product_code.strip(), version.strip(), assignments)

    @staticmethod
    def _row_number(row: Mapping[str, object], fallback: int) -> object:
        return row.get("_row_number", fallback)

    @staticmethod
    def _codes(row: Mapping[str, object]) -> tuple[str, str, str]:
        return (
            str(row.get("设备编码", "")).strip(),
            str(row["站位编码"]).strip(),
            str(row["物料编码"]).strip(),
        )
