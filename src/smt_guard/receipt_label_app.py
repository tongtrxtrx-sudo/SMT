"""Visible entry point for the standalone purchase-receipt label utility."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path
from tempfile import TemporaryDirectory

from PySide6.QtWidgets import QApplication

from smt_guard.receipt_labels import ReceiptLabelWorkspaceSettings
from smt_guard.ui.receipt_labels import ReceiptLabelWindow


def main(argv: Sequence[str] | None = None) -> int:
    """Start the standalone utility, optionally preloading one receipt workbook."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    smoke_test = "--smoke-test" in arguments
    paths = [argument for argument in arguments if argument != "--smoke-test"]
    if len(paths) > 1:
        raise ValueError(f"Unknown application argument: {paths[1]}")

    application = QApplication.instance()
    if application is None:
        application = QApplication([sys.argv[0], *arguments])
    if not isinstance(application, QApplication):
        raise RuntimeError("A non-GUI Qt application already exists")
    application.setApplicationName("SMT 物料标签库")

    if smoke_test:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            settings = ReceiptLabelWorkspaceSettings(
                root / "settings.json",
                root / "workspace",
            )
            window = ReceiptLabelWindow(workspace_settings=settings)
            if paths:
                window.load_receipt(Path(paths[0]))
            window.close()
        return 0
    window = ReceiptLabelWindow()
    if paths:
        window.load_receipt(Path(paths[0]))
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
