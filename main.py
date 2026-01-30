import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor
from mainwindow import MainWindow

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

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#2b2b2b"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#e0e0e0"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#3c3c3c"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#363636"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#404040"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#e0e0e0"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#4a9eff"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)
    app.setStyleSheet(DARK_STYLESHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
