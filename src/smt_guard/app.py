"""Application composition root and visible Windows entry point."""

import os
import sqlite3
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import QLocale
from PySide6.QtTextToSpeech import QTextToSpeech
from PySide6.QtWidgets import QApplication

from smt_guard.exporter import CsvRecordExporter
from smt_guard.feedback import (
    AnnouncementSink,
    AudioSink,
    FeedbackTone,
    SilentAnnouncementSink,
)
from smt_guard.importing import ConfigurationImportService
from smt_guard.operator import OperatorSession
from smt_guard.platform import (
    RunIdGenerator,
    WindowsAudioSink,
    WindowsSpeechSink,
    default_data_dir,
)
from smt_guard.sqlite import (
    SqliteAuditRepository,
    SqliteBomRepository,
    SqliteDatabase,
    SqliteMasterDataRepository,
    SqliteProductConfigurationRepository,
    SqliteProductionRunRepository,
)
from smt_guard.ui.audits import AuditLogWidget
from smt_guard.ui.boms import BomManagementWidget
from smt_guard.ui.configurations import ConfigurationManagementWidget
from smt_guard.ui.importing import ConfigurationImportWidget
from smt_guard.ui.main_window import MainWindow
from smt_guard.ui.master_data import DeviceStationWidget
from smt_guard.ui.operator import OperatorSessionWidget
from smt_guard.ui.records import RecordQueryWidget
from smt_guard.ui.runs import ProductionRunManagementWidget
from smt_guard.ui.scanning import ScanWidget
from smt_guard.xlsx_reader import OpenpyxlWorkbookReader


class ApplicationRuntime:
    """Own the composed window, repositories, and database connection."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        window: MainWindow,
        master_data: SqliteMasterDataRepository,
        configurations: SqliteProductConfigurationRepository,
        runs: SqliteProductionRunRepository,
        boms: SqliteBomRepository,
        audits: SqliteAuditRepository,
        operator_session: OperatorSession,
        scan_widget: ScanWidget,
        import_widget: ConfigurationImportWidget,
    ) -> None:
        self.connection = connection
        self.window = window
        self.master_data = master_data
        self.configurations = configurations
        self.runs = runs
        self.boms = boms
        self.audits = audits
        self.operator_session = operator_session
        self.scan_widget = scan_widget
        self.import_widget = import_widget
        self._closed = False

    def close(self) -> None:
        """Close UI resources and the database exactly once."""
        if self._closed:
            return
        self._closed = True
        try:
            self.scan_widget.interrupt_active_run("应用关闭")
        finally:
            self.window.close()
            self.connection.close()


def create_runtime(
    data_directory: Path,
    *,
    audio: AudioSink,
    announcements: AnnouncementSink | None = None,
    clock: Callable[[], datetime],
    run_id_factory: Callable[[], str],
) -> ApplicationRuntime:
    """Build the complete application against one persistent SQLite file."""
    data_directory.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(data_directory / "smt_guard.sqlite3")
    try:
        SqliteDatabase(connection).initialize()
        master_data = SqliteMasterDataRepository(connection)
        configurations = SqliteProductConfigurationRepository(connection)
        boms = SqliteBomRepository(connection)
        runs = SqliteProductionRunRepository(connection)
        audits = SqliteAuditRepository(connection)
        operator_session = OperatorSession()
        import_service = ConfigurationImportService(
            OpenpyxlWorkbookReader(),
            master_data,
            configurations,
            boms,
            operator_provider=operator_session.require,
        )

        announcer = announcements or SilentAnnouncementSink()
        operator_widget = OperatorSessionWidget(operator_session, announcer=announcer)
        master_data_widget = DeviceStationWidget(
            master_data, operator_provider=operator_session.require
        )
        import_widget = ConfigurationImportWidget(import_service, announcer=announcer)
        scan_widget = ScanWidget(
            configurations,
            runs,
            audio,
            clock=clock,
            run_id_factory=run_id_factory,
            runs=runs,
            operator_provider=operator_session.require,
            announcer=announcer,
        )
        bom_widget = BomManagementWidget(
            boms, operator_session.require, announcer=announcer
        )
        configuration_widget = ConfigurationManagementWidget(
            configurations, operator_session.require, announcer=announcer
        )
        run_widget = ProductionRunManagementWidget(
            runs,
            exporter=CsvRecordExporter(runs),
            announcer=announcer,
            clock=clock,
        )
        records_widget = RecordQueryWidget(
            runs, CsvRecordExporter(runs), announcer=announcer
        )
        audit_widget = AuditLogWidget(audits, clock=clock)
        import_widget.import_completed.connect(scan_widget.refresh_configurations)
        import_widget.import_completed.connect(configuration_widget.refresh)
        import_widget.bom_imported.connect(bom_widget.refresh)
        master_data_widget.master_data_changed.connect(scan_widget.refresh_configurations)
        master_data_widget.master_data_changed.connect(configuration_widget.refresh)
        configuration_widget.configurations_changed.connect(
            scan_widget.refresh_configurations
        )
        scan_widget.run_changed.connect(run_widget.refresh)
        window = MainWindow(
            scan_widget,
            master_data_widget,
            import_widget,
            bom_widget,
            configuration_widget,
            run_widget,
            records_widget,
            audit_widget,
            operator_widget,
        )
        run_widget.start_requested.connect(lambda: window.tab_widget.setCurrentIndex(0))
        for import_requester in (scan_widget, bom_widget, configuration_widget):
            import_requester.import_requested.connect(
                lambda: window.tab_widget.setCurrentIndex(window.IMPORT_TAB)
            )

        def resume_run(run_id: str) -> None:
            scan_widget.resume_run(run_id)
            window.tab_widget.setCurrentIndex(0)

        run_widget.resume_requested.connect(resume_run)
        run_widget.interrupt_requested.connect(scan_widget.interrupt_run)

        def operator_changed(_operator: str) -> None:
            scan_widget.interrupt_active_run("切换操作员")

        operator_widget.operator_changed.connect(operator_changed)
    except Exception:
        connection.close()
        raise

    return ApplicationRuntime(
        connection,
        window,
        master_data,
        configurations,
        runs,
        boms,
        audits,
        operator_session,
        scan_widget,
        import_widget,
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)


class _SilentAudioSink:
    """Suppress audio during packaged startup diagnostics."""

    def emit(self, tone: FeedbackTone) -> None:
        del tone


def _voice_announcements_enabled(environ: Mapping[str, str]) -> bool:
    value = environ.get("SMT_GUARD_VOICE_ENABLED", "1").strip().casefold()
    return value not in {"0", "false", "no", "off"}


def _create_chinese_speech_engine(engine_name: str) -> QTextToSpeech | None:
    try:
        engine = QTextToSpeech(engine_name)
        engine.setLocale(QLocale("zh_CN"))
        chinese_voice = next(
            (
                voice
                for voice in engine.availableVoices()
                if voice.locale().language() == QLocale.Language.Chinese
            ),
            None,
        )
        if chinese_voice is None:
            return None
        engine.setVoice(chinese_voice)
        engine.setRate(-0.3)
        engine.setVolume(1.0)
    except Exception:
        return None
    return engine


def _create_windows_announcer() -> AnnouncementSink:
    """Prefer the installed Chinese Windows voice without blocking the UI thread."""
    try:
        available_engines = QTextToSpeech.availableEngines()
    except Exception:
        return SilentAnnouncementSink()
    for engine_name in ("sapi", "winrt"):
        if engine_name not in available_engines:
            continue
        engine = _create_chinese_speech_engine(engine_name)
        if engine is None:
            continue
        return WindowsSpeechSink(
            engine.say,
            stopper=engine.stop,
            rate_setter=engine.setRate,
            volume_setter=engine.setVolume,
            engine_owner=engine,
        )
    return SilentAnnouncementSink()


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> int:
    """Start the visible Windows desktop application."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    unknown = [argument for argument in arguments if argument != "--smoke-test"]
    if unknown:
        raise ValueError(f"Unknown application argument: {unknown[0]}")
    smoke_test = "--smoke-test" in arguments

    application = QApplication.instance()
    if application is None:
        application = QApplication([sys.argv[0], *arguments])
    if not isinstance(application, QApplication):
        raise RuntimeError("A non-GUI Qt application already exists")

    clock = _utc_now
    effective_environment = dict(environ) if environ is not None else dict(os.environ)
    audio: AudioSink = _SilentAudioSink() if smoke_test else WindowsAudioSink()
    announcer = (
        SilentAnnouncementSink()
        if smoke_test or not _voice_announcements_enabled(effective_environment)
        else _create_windows_announcer()
    )
    runtime = create_runtime(
        default_data_dir(environ=environ),
        audio=audio,
        announcements=announcer,
        clock=clock,
        run_id_factory=RunIdGenerator(clock=clock),
    )
    if smoke_test:
        runtime.close()
        return 0
    runtime.window.show()
    try:
        return application.exec()
    finally:
        runtime.close()
