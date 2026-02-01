# -*- coding: utf-8 -*-
"""Виджет области перетаскивания файлов (drag-and-drop) с кнопкой «+»."""
import os
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel
from PySide6.QtCore import Qt

from constants import (
    COLOR_DROP_BORDER,
    COLOR_DROP_BG,
    COLOR_DROP_LABEL,
    COLOR_DROP_FONT_SIZE,
    FILE_DROP_MIN_HEIGHT,
    FILE_DROP_BORDER_RADIUS,
)


class FileDropArea(QFrame):
    """Область для перетаскивания файлов; при клике вызывается on_click (например, диалог выбора)."""
    def __init__(self, on_click, on_drop, allowed_exts, parent=None):
        super().__init__(parent)
        self._on_click = on_click
        self._on_drop = on_drop
        self._allowed_exts = {ext.lower() for ext in (allowed_exts or set())}
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(FILE_DROP_MIN_HEIGHT)
        self.setStyleSheet(
            f"QFrame {{"
            f"  border: 2px dashed {COLOR_DROP_BORDER};"
            f"  border-radius: {FILE_DROP_BORDER_RADIUS}px;"
            f"  background-color: {COLOR_DROP_BG};"
            f"}}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel("+")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet(f"color: {COLOR_DROP_LABEL}; font-size: {COLOR_DROP_FONT_SIZE}px; font-weight: bold;")
        layout.addWidget(label)

    def _firstValidPath(self, urls):
        for url in urls:
            path = url.toLocalFile()
            if not path or not os.path.isfile(path):
                continue
            ext = os.path.splitext(path)[1].lower()
            if not self._allowed_exts or ext in self._allowed_exts:
                return path
        return ""

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            path = self._firstValidPath(event.mimeData().urls())
            if path:
                event.acceptProposedAction()
                return
        event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            path = self._firstValidPath(event.mimeData().urls())
            if path:
                event.acceptProposedAction()
                return
        event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            path = self._firstValidPath(event.mimeData().urls())
            if path:
                self._on_drop(path)
                event.acceptProposedAction()
                return
        event.ignore()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._on_click()
        super().mousePressEvent(event)
