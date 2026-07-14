"""Application service for importing product station configurations."""

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from smt_guard.bom import BomDocument, BomImporter, BomVersion, WorkbookReader
from smt_guard.configuration import (
    ImportValidationError,
    MasterDataLookup,
    ProductConfigurationBuilder,
)
from smt_guard.scan import ProductConfiguration


class ConfigurationSink(Protocol):
    """Persistence boundary required by the import service."""

    def save(self, configuration: ProductConfiguration, *, actor: str = "SYSTEM") -> None:
        """Persist one validated product configuration."""
        ...


class BomSink(Protocol):
    """Optional persistent boundary for imported BOM versions."""

    def import_document(
        self,
        document: BomDocument,
        source_path: Path,
        *,
        operator: str,
        imported_at: datetime,
        version: str | None = None,
    ) -> BomVersion:
        """Persist an imported BOM as a new immutable draft version."""
        ...


@dataclass(frozen=True)
class ImportResult:
    """Imported BOM and configuration data used by the preview screen."""

    document: BomDocument
    configuration: ProductConfiguration


class ConfigurationImportService:
    """Read, validate, and persist BOM station assignments."""

    def __init__(
        self,
        reader: WorkbookReader,
        master_data: MasterDataLookup,
        configurations: ConfigurationSink,
        boms: BomSink | None = None,
        *,
        operator: str = "SYSTEM",
        operator_provider: Callable[[], str] | None = None,
    ) -> None:
        self._reader = reader
        self._master_data = master_data
        self._configurations = configurations
        self._boms = boms
        self._operator = operator
        self._operator_provider = operator_provider
        self._document: BomDocument | None = None
        self._bom_version_id: int | None = None

    def import_bom(self, bom_path: Path, *, version: str | None = None) -> BomDocument:
        """Load and retain one validated BOM for a later station-table import."""
        self._document = None
        self._bom_version_id = None
        document = BomImporter(self._reader).import_xlsx(bom_path)
        if self._boms is not None:
            operator = self._current_operator()
            stored = self._boms.import_document(
                document,
                bom_path,
                operator=operator,
                imported_at=datetime.now(UTC),
                version=version,
            )
            self._bom_version_id = stored.id
        self._document = document
        return document

    def import_station_table(
        self,
        station_path: Path,
        *,
        version: str,
        station_sheet: str,
    ) -> ImportResult:
        """Validate a station table against the BOM loaded in this application session."""
        document = self._document
        if document is None:
            raise ImportValidationError("Import a BOM before importing a station table")

        normalized_version = version.strip()
        if not normalized_version:
            raise ImportValidationError("Product configuration version is required")
        normalized_sheet = station_sheet.strip()
        if not normalized_sheet:
            raise ImportValidationError("Station worksheet name is required")

        station_rows = self._reader.read_sheet(station_path, normalized_sheet)
        configuration = ProductConfigurationBuilder(self._master_data).build(
            document.product.material_code,
            normalized_version,
            document.materials,
            station_rows,
        )
        configuration = replace(configuration, bom_version_id=self._bom_version_id)
        self._configurations.save(configuration, actor=self._current_operator())
        return ImportResult(document, configuration)

    def _current_operator(self) -> str:
        if self._operator_provider is not None:
            return self._operator_provider()
        return self._operator.strip() or "SYSTEM"

    def import_files(
        self,
        bom_path: Path,
        station_path: Path,
        *,
        version: str,
        station_sheet: str,
    ) -> ImportResult:
        """Import both files in sequence for compatibility with existing integrations."""
        self.import_bom(bom_path)
        return self.import_station_table(
            station_path,
            version=version,
            station_sheet=station_sheet,
        )
