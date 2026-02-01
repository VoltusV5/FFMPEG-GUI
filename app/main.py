"""Точка входа приложения: настройка темы, создание главного окна."""
import sys
import os
import logging

from app.constants import (
    COLOR_WINDOW, COLOR_WINDOW_TEXT, COLOR_BASE, COLOR_ALTERNATE_BASE,
    COLOR_BUTTON, COLOR_HIGHLIGHT, COLOR_HIGHLIGHTED_TEXT,
)


def _setup_runtime_paths():
    """Если рядом есть bin/, добавляет его в PATH/sys.path (для dll/pyd)."""
    app_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bin_dir = os.path.join(app_dir, "bin")
    if not os.path.isdir(bin_dir):
        return
    if bin_dir not in sys.path:
        sys.path.insert(0, bin_dir)
    os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
    try:
        if os.name == "nt":
            os.add_dll_directory(bin_dir)
    except Exception:
        pass


_setup_runtime_paths()

# PySide6 imports after runtime path setup
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QPalette, QColor
from PySide6.QtCore import QStandardPaths


def _pick_log_path():
    """Выбирает путь для app.log (корень проекта или AppData, если нет прав)."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    preferred = os.path.join(project_root, "app.log")
    try:
        with open(preferred, "a", encoding="utf-8"):
            pass
        return preferred
    except Exception:
        pass
    user_dir = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation) or os.path.expanduser("~")
    try:
        os.makedirs(user_dir, exist_ok=True)
    except Exception:
        user_dir = os.path.expanduser("~")
    return os.path.join(user_dir, "app.log")


def setup_logging():
    """Логирование в app.log (корень проекта или AppData)."""
    log_path = _pick_log_path()
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if any(isinstance(h, logging.FileHandler) for h in root.handlers):
        return
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(formatter)
    root.addHandler(handler)


def _patch_silent_message_boxes():
    """Отключает системные звуки у QMessageBox, используя не‑native диалоги."""
    def _show_box(icon, parent, title, text, buttons=QMessageBox.Ok, default_button=QMessageBox.NoButton):
        box = QMessageBox(parent)
        box.setIcon(icon)
        box.setWindowTitle(title)
        box.setText(text)
        box.setStandardButtons(buttons)
        if default_button != QMessageBox.NoButton:
            box.setDefaultButton(default_button)
        box.setOption(QMessageBox.DontUseNativeDialog, True)
        return box.exec()

    def _info(parent, title, text, buttons=QMessageBox.Ok, default_button=QMessageBox.NoButton):
        return _show_box(QMessageBox.Information, parent, title, text, buttons, default_button)

    def _warn(parent, title, text, buttons=QMessageBox.Ok, default_button=QMessageBox.NoButton):
        return _show_box(QMessageBox.Warning, parent, title, text, buttons, default_button)

    def _crit(parent, title, text, buttons=QMessageBox.Ok, default_button=QMessageBox.NoButton):
        return _show_box(QMessageBox.Critical, parent, title, text, buttons, default_button)

    def _question(parent, title, text, buttons=QMessageBox.Yes | QMessageBox.No, default_button=QMessageBox.NoButton):
        return _show_box(QMessageBox.Question, parent, title, text, buttons, default_button)

    QMessageBox.information = _info
    QMessageBox.warning = _warn
    QMessageBox.critical = _crit
    QMessageBox.question = _question


# Тёмно-серая тема: фон #2b2b2b, панели #363636, акцент #4a9eff, текст #e0e0e0
DARK_STYLESHEET = """
    QMainWindow, QWidget { background-color: #2b2b2b; }
    QWidget { color: #e0e0e0; }
    QLabel { color: #e0e0e0; }
    QPushButton {
        background-color: #404040;
        color: #e0e0e0;
        border: 1px solid #505050;
        border-radius: 4px;
        padding: 6px 12px;
        min-height: 20px;
    }
    QPushButton:hover {
        background-color: #4a4a4a;
        border-color: #606060;
    }
    QPushButton:pressed {
        background-color: #353535;
    }
    QPushButton:disabled {
        background-color: #303030;
        color: #6e6e6e;
        border-color: #404040;
    }
    QPushButton:checked {
        background-color: #4a9eff;
        color: #ffffff;
        border-color: #3a8eef;
    }
    QPushButton:checked:hover {
        background-color: #5aaeff;
        border-color: #4a9eff;
    }
    QAbstractScrollArea::viewport {
        background-color: #363636;
    }
    QTableWidget {
        background-color: #363636;
        color: #e0e0e0;
        gridline-color: #505050;
        border: 1px solid #505050;
        border-radius: 4px;
    }
    QTableWidget::item {
        background-color: #363636;
        color: #e0e0e0;
        padding: 4px;
    }
    QTableWidget::item:alternate {
        background-color: #3a3a3a;
    }
    QTableWidget::item:selected {
        background-color: #4a9eff;
        color: #ffffff;
    }
    QHeaderView::section {
        background-color: #404040;
        color: #e0e0e0;
        border: none;
        border-right: 1px solid #505050;
        border-bottom: 1px solid #505050;
        padding: 6px 8px;
    }
    QTextEdit, QLineEdit, QPlainTextEdit {
        background-color: #3c3c3c;
        color: #e0e0e0;
        border: 1px solid #505050;
        border-radius: 4px;
        padding: 6px;
        selection-background-color: #4a9eff;
        font-family: Consolas, monospace;
    }
    QSlider::groove:horizontal {
        border: none;
        height: 6px;
        background: #505050;
        border-radius: 3px;
    }
    QSlider::handle:horizontal {
        background: #4a9eff;
        width: 14px;
        margin: -4px 0;
        border-radius: 7px;
    }
    QSlider::handle:horizontal:hover {
        background: #6ab0ff;
    }
    QSlider::sub-page:horizontal {
        background: #4a9eff;
        border-radius: 3px;
    }
    QProgressBar {
        border: 1px solid #505050;
        border-radius: 4px;
        text-align: center;
        background-color: #3c3c3c;
        color: #e0e0e0;
    }
    QProgressBar::chunk {
        background-color: #4a9eff;
        border-radius: 3px;
    }
    QMenuBar {
        background-color: #363636;
        color: #e0e0e0;
    }
    QMenuBar::item:selected {
        background-color: #4a9eff;
        color: #ffffff;
    }
    QMenu {
        background-color: #363636;
        color: #e0e0e0;
        border: 1px solid #505050;
    }
    QMenu::item:selected {
        background-color: #4a9eff;
        color: #ffffff;
    }
    QStatusBar {
        background-color: #363636;
        color: #9e9e9e;
        border-top: 1px solid #505050;
    }
    QComboBox {
        background-color: #3c3c3c;
        color: #e0e0e0;
        border: 1px solid #505050;
        border-radius: 4px;
        padding: 4px 8px;
        min-height: 20px;
    }
    QComboBox:hover {
        border-color: #606060;
    }
    QComboBox::drop-down {
        border: none;
        background: #404040;
        width: 20px;
        border-radius: 0 4px 4px 0;
    }
    QComboBox QAbstractItemView {
        background-color: #363636;
        color: #e0e0e0;
        selection-background-color: #4a9eff;
    }
    QGroupBox {
        color: #e0e0e0;
        border: 1px solid #505050;
        border-radius: 4px;
        margin-top: 8px;
        padding-top: 8px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 8px;
        padding: 0 4px;
        background-color: #2b2b2b;
    }
    QTabWidget::pane {
        border: 1px solid #505050;
        background-color: #363636;
        border-radius: 4px;
        top: -1px;
    }
    QTabBar::tab {
        background-color: #404040;
        color: #e0e0e0;
        border: 1px solid #505050;
        border-bottom: none;
        padding: 6px 14px;
        margin-right: 2px;
    }
    QTabBar::tab:selected {
        background-color: #363636;
        border-bottom: 1px solid #363636;
    }
    QTabBar::tab:hover:!selected {
        background-color: #4a4a4a;
    }
    QToolTip {
        background-color: #404040;
        color: #e0e0e0;
        border: 1px solid #505050;
        padding: 4px;
    }
    QCheckBox, QRadioButton {
        color: #e0e0e0;
    }
    QSpinBox, QDoubleSpinBox {
        background-color: #3c3c3c;
        color: #e0e0e0;
        border: 1px solid #505050;
        border-radius: 4px;
        padding: 4px;
        min-height: 20px;
    }
"""


def main():
    """Запуск приложения."""
    setup_logging()
    app = QApplication(sys.argv)
    _patch_silent_message_boxes()
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(COLOR_WINDOW))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(COLOR_WINDOW_TEXT))
    palette.setColor(QPalette.ColorRole.Base, QColor(COLOR_BASE))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(COLOR_ALTERNATE_BASE))
    palette.setColor(QPalette.ColorRole.Button, QColor(COLOR_BUTTON))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(COLOR_WINDOW_TEXT))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(COLOR_HIGHLIGHT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(COLOR_HIGHLIGHTED_TEXT))
    app.setPalette(palette)
    app.setStyleSheet(DARK_STYLESHEET)
    from app.mainwindow import MainWindow
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
