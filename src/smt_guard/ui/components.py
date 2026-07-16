"""Reusable visual building blocks for SMT Guard management pages."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)


class PageHeader(QWidget):
    """Display a consistent page title and one-line task description."""

    def __init__(
        self,
        title: str,
        subtitle: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("pageTitle")
        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setObjectName("pageSubtitle")
        self.subtitle_label.setWordWrap(True)
        layout.addWidget(self.title_label)
        layout.addWidget(self.subtitle_label)


class EmptyState(QFrame):
    """Explain an empty result and optionally expose the next useful action."""

    action_requested = Signal()

    def __init__(
        self,
        title: str,
        description: str,
        *,
        action_text: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("emptyState")
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(8)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("emptyStateTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.description_label = QLabel(description)
        self.description_label.setObjectName("emptyStateDescription")
        self.description_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.description_label.setWordWrap(True)
        self.action_button = QPushButton(action_text)
        self.action_button.setProperty("actionRole", "primary")
        self.action_button.setVisible(bool(action_text))
        self.action_button.clicked.connect(self.action_requested.emit)
        layout.addStretch(1)
        layout.addWidget(self.title_label)
        layout.addWidget(self.description_label)
        layout.addWidget(self.action_button, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addStretch(1)

    def set_message(self, title: str, description: str) -> None:
        self.title_label.setText(title)
        self.description_label.setText(description)


def content_card(*, object_name: str = "contentCard") -> QFrame:
    """Return a plain card frame that receives the shared application style."""
    card = QFrame()
    card.setObjectName(object_name)
    return card


def section_heading(title: str, description: str = "") -> QWidget:
    """Return a compact section heading for cards and split panes."""
    widget = QWidget()
    layout = QHBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    title_label = QLabel(title)
    title_label.setObjectName("sectionTitle")
    layout.addWidget(title_label)
    if description:
        description_label = QLabel(description)
        description_label.setObjectName("sectionDescription")
        layout.addWidget(description_label)
    layout.addStretch(1)
    return widget


def prepare_table(table: QTableWidget) -> None:
    """Apply the common read-friendly behavior to data tables."""
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(34)
    table.setShowGrid(False)


def set_feedback(label: QLabel, state: str, message: str) -> None:
    """Render non-blocking status feedback with a consistent semantic state."""
    colors = {
        "success": ("#ecfdf3", "#067647", "#abefc6"),
        "error": ("#fef3f2", "#b42318", "#fecdca"),
        "warning": ("#fffaeb", "#b54708", "#fedf89"),
        "neutral": ("#f2f4f7", "#344054", "#e4e7ec"),
    }
    background, color, border = colors.get(state, colors["neutral"])
    label.setProperty("feedbackState", state)
    label.setStyleSheet(
        f"background-color: {background}; color: {color}; "
        f"border: 1px solid {border}; border-radius: 6px; padding: 7px 10px;"
    )
    label.setText(message)
