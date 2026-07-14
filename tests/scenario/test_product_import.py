import unittest
from pathlib import Path

from smt_guard.bom import BomImporter


class FakeWorkbookReader:
    def __init__(self, rows: list[dict[str, str]]) -> None:
        self.rows = rows
        self.received_path: Path | None = None

    def read_sheet(self, path: Path, sheet_name: str) -> list[dict[str, str]]:
        self.received_path = path
        if sheet_name != "Worksheet":
            raise AssertionError("Unexpected sheet name")
        return self.rows


class ProductImportTests(unittest.TestCase):
    def sample_rows(self) -> list[dict[str, str]]:
        return [
            {
                "BOM编号": "立升铁葫芦",
                "BOM名称": "立升铁葫芦大板",
                "深度": "0",
                "单位用量": "1",
                "商品编号": "501000087",
                "商品名": "控制板",
                "商品规格": "大板加小灯板",
                "商品分类": "",
            },
            {
                "BOM编号": "",
                "BOM名称": "",
                "深度": "1",
                "单位用量": "1",
                "商品编号": "013000081",
                "商品名": "3P双头反向端子线",
                "商品规格": "26AWG",
                "商品分类": "电子物料/电子线",
            },
            {
                "BOM编号": "",
                "BOM名称": "",
                "深度": "1",
                "单位用量": "2",
                "商品编号": "005000103",
                "商品名": "贴片电阻",
                "商品规格": "1206 2R ±5%",
                "商品分类": "电子物料/电阻",
            },
        ]

    def test_imports_supplied_workbook_shape(self) -> None:
        reader = FakeWorkbookReader(self.sample_rows())
        importer = BomImporter(reader)

        document = importer.import_xlsx(Path("商品BOM_导出.xlsx"))

        self.assertEqual(Path("商品BOM_导出.xlsx"), reader.received_path)
        self.assertEqual("501000087", document.product.material_code)
        self.assertEqual("立升铁葫芦", document.product.bom_number)
        self.assertEqual("立升铁葫芦大板", document.product.bom_name)

    def test_preserves_leading_zeroes_in_material_codes(self) -> None:
        importer = BomImporter(FakeWorkbookReader(self.sample_rows()))

        document = importer.import_xlsx(Path("商品BOM_导出.xlsx"))

        self.assertIn("013000081", document.materials)
        self.assertNotIn("13000081", document.materials)

    def test_maps_component_fields(self) -> None:
        importer = BomImporter(FakeWorkbookReader(self.sample_rows()))

        material = importer.import_xlsx(Path("bom.xlsx")).materials["005000103"]

        self.assertEqual("贴片电阻", material.name)
        self.assertEqual("1206 2R ±5%", material.specification)
        self.assertEqual("2", material.quantity)
        self.assertEqual("电子物料/电阻", material.category)

    def test_keeps_non_smt_components_as_bom_candidates(self) -> None:
        importer = BomImporter(FakeWorkbookReader(self.sample_rows()))

        document = importer.import_xlsx(Path("bom.xlsx"))

        self.assertIn("013000081", document.materials)
        self.assertEqual(2, len(document.materials))


if __name__ == "__main__":
    unittest.main()
