"""Device and station master-data management."""

import re
from dataclasses import dataclass

_CODE_PART_PATTERN = re.compile(r"\d+|\D+")


def normalize_code(value: str) -> str:
    """Remove scanner or form whitespace while preserving code characters."""
    return value.strip()


def natural_code_key(value: str) -> tuple[tuple[int, int, str], ...]:
    """Sort embedded digit groups numerically while preserving text prefixes."""
    return tuple(
        (1, int(part), part) if part.isdecimal() else (0, 0, part.casefold())
        for part in _CODE_PART_PATTERN.findall(value)
    )


class MasterDataError(ValueError):
    """Base error for invalid master-data operations."""


class DuplicateCodeError(MasterDataError):
    """Raised when a device or station code already exists."""


class UnknownEntityError(MasterDataError):
    """Raised when a requested device or station does not exist."""


class ReferencedEntityError(MasterDataError):
    """Raised when deleting master data that is already referenced."""


@dataclass
class Device:
    """A physical placement-machine device or machine area."""

    code: str
    name: str
    line: str
    enabled: bool = True
    archived: bool = False


@dataclass
class Station:
    """A physical feeder station belonging to one device."""

    device_code: str
    code: str
    enabled: bool = True
    referenced: bool = False
    name: str = ""
    archived: bool = False


class MasterDataService:
    """Manage devices and stations with deterministic uniqueness rules."""

    def __init__(self) -> None:
        self._devices: dict[str, Device] = {}
        self._stations: dict[tuple[str, str], Station] = {}

    def add_device(self, code: str, name: str, line: str) -> Device:
        normalized = normalize_code(code)
        if normalized in self._devices:
            raise DuplicateCodeError(f"Duplicate device code: {normalized}")
        device = Device(normalized, name.strip(), line.strip())
        self._devices[normalized] = device
        return device

    def disable_device(self, code: str) -> None:
        self.get_device(code).enabled = False

    def enable_device(self, code: str) -> None:
        device = self.get_device(code)
        if device.archived:
            raise MasterDataError(f"Archived device cannot be enabled: {device.code}")
        device.enabled = True

    def update_device(self, code: str, *, name: str, line: str) -> Device:
        device = self.get_device(code)
        device.name = name.strip()
        device.line = line.strip()
        return device

    def get_device(self, code: str) -> Device:
        normalized = normalize_code(code)
        try:
            return self._devices[normalized]
        except KeyError as error:
            raise UnknownEntityError(f"Unknown device: {normalized}") from error

    def is_device_enabled(self, code: str) -> bool:
        try:
            return self.get_device(code).enabled
        except UnknownEntityError:
            return False

    def add_station(self, device_code: str, station_code: str) -> Station:
        device = self.get_device(device_code)
        normalized = normalize_code(station_code)
        key = (device.code, normalized)
        if key in self._stations:
            raise DuplicateCodeError(f"Duplicate station code: {device.code}/{normalized}")
        station = Station(device.code, normalized)
        self._stations[key] = station
        return station

    def bulk_add_stations(
        self,
        device_code: str,
        prefix: str,
        start: int,
        end: int,
        *,
        width: int,
    ) -> list[Station]:
        device = self.get_device(device_code)
        codes = [f"{prefix}{number:0{width}d}" for number in range(start, end + 1)]
        duplicates = [code for code in codes if (device.code, code) in self._stations]
        if duplicates:
            raise DuplicateCodeError(f"Duplicate station code: {device.code}/{duplicates[0]}")
        return [self.add_station(device.code, code) for code in codes]

    def get_station(self, device_code: str, station_code: str) -> Station:
        key = (normalize_code(device_code), normalize_code(station_code))
        try:
            return self._stations[key]
        except KeyError as error:
            raise UnknownEntityError(f"Unknown station: {key[0]}/{key[1]}") from error

    def list_stations(self, device_code: str) -> list[Station]:
        normalized = self.get_device(device_code).code
        stations = [
            station for key, station in self._stations.items() if key[0] == normalized
        ]
        return sorted(stations, key=lambda station: natural_code_key(station.code))

    def is_station_enabled(self, device_code: str, station_code: str) -> bool:
        try:
            return self.get_station(device_code, station_code).enabled
        except UnknownEntityError:
            return False

    def disable_station(self, device_code: str, station_code: str) -> None:
        self.get_station(device_code, station_code).enabled = False

    def enable_station(self, device_code: str, station_code: str) -> None:
        station = self.get_station(device_code, station_code)
        if station.archived:
            raise MasterDataError(
                f"Archived station cannot be enabled: {station.device_code}/{station.code}"
            )
        station.enabled = True

    def update_station(
        self, device_code: str, station_code: str, *, name: str
    ) -> Station:
        station = self.get_station(device_code, station_code)
        station.name = name.strip()
        return station

    def mark_station_referenced(self, device_code: str, station_code: str) -> None:
        self.get_station(device_code, station_code).referenced = True

    def delete_station(self, device_code: str, station_code: str) -> None:
        station = self.get_station(device_code, station_code)
        if station.referenced:
            raise ReferencedEntityError(
                f"Referenced station cannot be deleted: {device_code}/{station_code}"
            )
        del self._stations[(station.device_code, station.code)]

    def archive_station(self, device_code: str, station_code: str) -> None:
        station = self.get_station(device_code, station_code)
        station.enabled = False
        station.archived = True

    def archive_device(self, code: str) -> None:
        device = self.get_device(code)
        device.enabled = False
        device.archived = True
        for station in self.list_stations(device.code):
            station.enabled = False
            station.archived = True
