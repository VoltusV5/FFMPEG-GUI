# -*- coding: utf-8 -*-
"""Виджет полоски под слайдером: подсвечивает области обрезки (keep/trim)."""
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QColor

from app.constants import (
    HEIGHT_TRIM_SEGMENT_BAR,
    TRIM_BAR_MIN_WIDTH,
    TRIM_BAR_RADIUS,
    TRIM_BAR_IN_MARK_MIN,
    TRIM_BAR_IN_MARK_MAX,
    TRIM_BAR_IN_MARK_DIV,
    COLOR_BG_STRIP,
    COLOR_KEEP_SEGMENT,
    COLOR_TRIM_ACCENT,
)


class TrimSegmentBar(QWidget):
    """Полоска под слайдером: подсвечивает области обрезки (зелёный — добавленные, синий — текущий in–out)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(HEIGHT_TRIM_SEGMENT_BAR)
        self.setMinimumWidth(TRIM_BAR_MIN_WIDTH)
        self.duration_sec = 0.0
        self.keep_segments = []  # [(start, end), ...]
        self.trim_start_sec = None
        self.trim_end_sec = None

    def updateSegments(self, duration_sec, keep_segments, trim_start_sec, trim_end_sec):
        self.duration_sec = duration_sec or 0.0
        self.keep_segments = list(keep_segments or [])
        self.trim_start_sec = trim_start_sec
        self.trim_end_sec = trim_end_sec
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.duration_sec <= 0:
            return
        w, h = self.width(), self.height()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        radius = min(TRIM_BAR_RADIUS, h // 2)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.fillRect(0, 0, w, h, QColor(*COLOR_BG_STRIP))
        for start, end in self.keep_segments:
            if end <= start:
                continue
            x1 = int(w * start / self.duration_sec)
            x2 = int(w * end / self.duration_sec)
            x1 = max(0, min(x1, w))
            x2 = max(0, min(x2, w))
            if x2 > x1:
                seg_w = x2 - x1
                r = min(radius, seg_w // 2, h // 2)
                painter.setBrush(QColor(*COLOR_KEEP_SEGMENT))
                painter.drawRoundedRect(QRectF(x1, 0, seg_w, h), r, r)
        if self.trim_start_sec is not None and self.trim_end_sec is not None and self.trim_end_sec > self.trim_start_sec:
            x1 = int(w * self.trim_start_sec / self.duration_sec)
            x2 = int(w * self.trim_end_sec / self.duration_sec)
            x1 = max(0, min(x1, w))
            x2 = max(0, min(x2, w))
            if x2 > x1:
                seg_w = x2 - x1
                r = min(radius, seg_w // 2, h // 2)
                painter.setBrush(QColor(*COLOR_TRIM_ACCENT))
                painter.drawRoundedRect(QRectF(x1, 0, seg_w, h), r, r)
        elif self.trim_start_sec is not None:
            x_in = int(w * self.trim_start_sec / self.duration_sec)
            x_in = max(0, min(x_in, w))
            painter.setBrush(QColor(*COLOR_TRIM_ACCENT))
            in_w = max(TRIM_BAR_IN_MARK_MIN, min(TRIM_BAR_IN_MARK_MAX, w // TRIM_BAR_IN_MARK_DIV))
            painter.drawRect(x_in, 0, in_w, h)
        painter.end()
