from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Protocol


class BomImportError(ValueError):
    """Raised when BOM rows cannot be mapped into a product document."""


class WorkbookReader(Protocol):
    """Boundary for reading tabular rows from a workbook."""

    def read_sheet(self, path: Path, sheet_name: str) -> Sequence[Mapping[str, object]]:
        """Read one worksheet as dictionaries keyed by header text."""
        ...


@dataclass(frozen=True)
class Product:
    """Finished product identified by the depth-zero BOM row."""

    material_code: str
    bom_number: str
    bom_name: str
    name: str
    specification: str


@dataclass(frozen=True)
class Material:
    """Candidate component material from the BOM."""

    code: str
    name: str
    specification: str
    quantity: str
    category: str


@dataclass(frozen=True)
class BomDocument:
    """Mapped product and component materials."""

    product: Product
    materials: dict[str, Material]


class BomStatus(Enum):
    """Lifecycle state for an immutable BOM version."""

    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ACTIVE = "ACTIVE"
    OBSOLETE = "OBSOLETE"
    ARCHIVED = "ARCHIVED"


@dataclass(frozen=True)
class BomVersion:
    """Persisted BOM version and import provenance."""

    id: int
    version: str
    document: BomDocument
    status: BomStatus
    source_filename: str
    source_sha256: str
    imported_at: datetime
    imported_by: str
    published_at: datetime | None = None
    activated_at: datetime | None = None


class BomImporter:
    """Map the known Chinese ERP BOM export into domain objects."""

    def __init__(self, reader: WorkbookReader) -> None:
        self._reader = reader

    def import_xlsx(self, path: Path) -> BomDocument:
        rows = self._reader.read_sheet(path, "Worksheet")
        product: Product | None = None
        materials: dict[str, Material] = {}

        for row in rows:
            depth = self._text(row, "深度")
            code = self._text(row, "商品编号")
            if depth == "0":
                product = self._map_product(row, code)
            elif depth and depth != "0" and code:
                materials[code] = self._map_material(row, code)

        if product is None or not product.material_code:
            raise BomImportError("BOM does not contain a valid depth-zero product row")
        return BomDocument(product=product, materials=materials)

    @staticmethod
    def _text(row: Mapping[str, object], column: str) -> str:
        return str(row.get(column, "")).strip()

    @classmethod
    def _map_product(cls, row: Mapping[str, object], code: str) -> Product:
        return Product(
            material_code=code,
            bom_number=cls._text(row, "BOM编号"),
            bom_name=cls._text(row, "BOM名称"),
            name=cls._text(row, "商品名"),
            specification=cls._text(row, "商品规格"),
        )

    @classmethod
    def _map_material(cls, row: Mapping[str, object], code: str) -> Material:
        return Material(
            code=code,
            name=cls._text(row, "商品名"),
            specification=cls._text(row, "商品规格"),
            quantity=cls._text(row, "单位用量"),
            category=cls._text(row, "商品分类"),
        )
