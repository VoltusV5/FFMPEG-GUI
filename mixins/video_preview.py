"""Миксин: предпросмотр видео, полоска обрезки, таймер времени."""

import logging
from PySide6.QtWidgets import QVBoxLayout, QStyleOptionSlider, QStyle
from PySide6.QtCore import Qt, QUrl, QEvent, QTimer
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget as QVideoWidgetBase

from app.constants import FRAME_STEP_MS
from widgets import TrimSegmentBar

logger = logging.getLogger(__name__)


class VideoPreviewMixin:
    """Миксин: инициализация плеера, загрузка видео, seek, trim/keep, полоска обрезки, отображение времени."""

    def initVideoPreview(self):
        """Инициализирует медиаплеер для предпросмотра видео"""
        try:
            self.mediaPlayer = QMediaPlayer(self)
            self.audioOutput = QAudioOutput(self)
            self.mediaPlayer.setAudioOutput(self.audioOutput)

            if hasattr(self.ui, 'videoPreviewWidget'):
                self.ui.videoPreviewWidget.setFixedSize(384, 216)
                if hasattr(self.ui, 'verticalLayout'):
                    self.ui.verticalLayout.setContentsMargins(16, 0, 0, 0)
                self.videoWidget = QVideoWidgetBase(self.ui.videoPreviewWidget)
                self.videoWidget.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
                layout = QVBoxLayout(self.ui.videoPreviewWidget)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.addWidget(self.videoWidget)
                self.mediaPlayer.setVideoOutput(self.videoWidget)

            self.mediaPlayer.durationChanged.connect(self.onVideoDurationChanged)
            self.mediaPlayer.positionChanged.connect(self.onVideoPositionChanged)
            self.mediaPlayer.playbackStateChanged.connect(self.onVideoPlaybackStateChanged)
            self.mediaPlayer.mediaStatusChanged.connect(self.onVideoMediaStatusChanged)

            self.audioOutput.setVolume(1.0)
            self.isMuted = False

            if hasattr(self.ui, 'verticalLayout') and hasattr(self.ui, 'videoTimelineSlider'):
                self.trimSegmentBar = TrimSegmentBar(self.ui.videoTimelineSlider.parent())
                self.ui.verticalLayout.insertWidget(2, self.trimSegmentBar)
                self._updateTrimSegmentBar()
            if hasattr(self.ui, 'videoTimelineSlider'):
                self.ui.videoTimelineSlider.installEventFilter(self)
        except Exception:
            logger.exception("Ошибка инициализации медиаплеера")
            self.mediaPlayer = None
        if not hasattr(self, 'trimSegmentBar'):
            self.trimSegmentBar = None

    def _updateTrimSegmentBar(self):
        """Обновляет полоску сегментов обрезки по выделенному файлу и длительности видео."""
        if not getattr(self, 'trimSegmentBar', None):
            return
        item = self.getSelectedQueueItem()
        duration = getattr(self, 'videoDuration', 0) or 0
        if not item or duration <= 0:
            self.trimSegmentBar.updateSegments(0, [], None, None)
            return
        keep = getattr(item, 'keep_segments', []) or []
        start = getattr(item, 'trim_start_sec', None)
        end = getattr(item, 'trim_end_sec', None)
        self.trimSegmentBar.updateSegments(duration, keep, start, end)

    def loadVideoForPreview(self):
        """Загружает видео в медиаплеер для предпросмотра; после загрузки показывается первый кадр."""
        item = self.getSelectedQueueItem()
        if not self.mediaPlayer or not item:
            return
        try:
            self.mediaPlayer.stop()
            url = QUrl.fromLocalFile(item.file_path)
            self.mediaPlayer.setSource(url)
            self.inputFile = item.file_path
        except Exception:
            logger.exception("Ошибка загрузки видео")

    def onVideoMediaStatusChanged(self, status):
        """После загрузки медиа показываем первый кадр (позиция 0, пауза)."""
        if status == QMediaPlayer.MediaStatus.LoadedMedia or status == QMediaPlayer.MediaStatus.BufferedMedia:
            if self.mediaPlayer:
                self.mediaPlayer.setPosition(0)
                self.mediaPlayer.pause()
                if hasattr(self.ui, 'videoPlayButton'):
                    self.ui.videoPlayButton.setText("Play")

    def toggleVideoPlayback(self):
        if not self.mediaPlayer:
            return
        if self.mediaPlayer.playbackState() == QMediaPlayer.PlayingState:
            self.mediaPlayer.pause()
            if hasattr(self.ui, 'videoPlayButton'):
                self.ui.videoPlayButton.setText("Play")
        else:
            self.mediaPlayer.play()
            if hasattr(self.ui, 'videoPlayButton'):
                self.ui.videoPlayButton.setText("Pause")

    def stepVideoPreviousFrame(self):
        if not self.mediaPlayer or self.videoDuration <= 0:
            return
        pos_ms = self.mediaPlayer.position()
        self.mediaPlayer.setPosition(max(0, pos_ms - FRAME_STEP_MS))

    def stepVideoNextFrame(self):
        if not self.mediaPlayer or self.videoDuration <= 0:
            return
        pos_ms = self.mediaPlayer.position()
        duration_ms = int(self.videoDuration * 1000)
        self.mediaPlayer.setPosition(min(duration_ms, pos_ms + FRAME_STEP_MS))

    def setTrimStart(self):
        item = self.getSelectedQueueItem()
        if not item or not self.mediaPlayer:
            return
        item.trim_start_sec = self.mediaPlayer.position() / 1000.0
        self._updateTrimSegmentBar()

    def setTrimEnd(self):
        item = self.getSelectedQueueItem()
        if not item or not self.mediaPlayer:
            return
        item.trim_end_sec = self.mediaPlayer.position() / 1000.0
        self._updateTrimSegmentBar()
        self.updateCommandFromGUI()

    def addKeepArea(self):
        item = self.getSelectedQueueItem()
        if not item:
            return
        start = getattr(item, "trim_start_sec", None)
        end = getattr(item, "trim_end_sec", None)
        if start is not None and end is not None and end > start:
            if not getattr(item, "keep_segments", None):
                item.keep_segments = []
            item.keep_segments.append((start, end))
        pos_sec = self.mediaPlayer.position() / 1000.0 if self.mediaPlayer else 0
        item.trim_start_sec = pos_sec
        item.trim_end_sec = pos_sec
        self._updateTrimSegmentBar()

    def _setVideoPlayerTooltips(self):
        tooltips = {
            "videoPlayButton": "Воспроизведение / пауза",
            "PreviousFrame": "Предыдущий кадр",
            "NextFrame": "Следующий кадр",
            "videoTimelineSlider": "Перемотка по времени",
            "videoTimeLabel": "",
            "videoMuteButton": "Вкл/выкл звук",
            "AddKeepArea": "Добавить область склейки (текущий in–out)",
            "SetInPoint": "Поставить начало оставляемого промежутка (In) на текущем кадре",
            "SetOutPoint": "Поставить конец оставляемого промежутка (Out) на текущем кадре",
        }
        for name, text in tooltips.items():
            if text and hasattr(self.ui, name):
                getattr(self.ui, name).setToolTip(text)

    def toggleVideoMute(self):
        if not self.audioOutput:
            return
        self.isMuted = not self.isMuted
        self.audioOutput.setMuted(self.isMuted)
        if hasattr(self.ui, 'videoMuteButton'):
            self.ui.videoMuteButton.setText("🔇" if self.isMuted else "🔊")

    def seekVideo(self, position):
        if not self.mediaPlayer or self.videoDuration <= 0:
            return
        max_value = self.ui.videoTimelineSlider.maximum()
        time_ms = int((position / max_value) * self.videoDuration * 1000)
        self.mediaPlayer.setPosition(time_ms)

    def pauseVideoForSeek(self):
        if not self.mediaPlayer:
            return
        self.wasPlayingBeforeSeek = (self.mediaPlayer.playbackState() == QMediaPlayer.PlayingState)
        if self.wasPlayingBeforeSeek:
            self.mediaPlayer.pause()

    def resumeVideoAfterSeek(self):
        if not self.mediaPlayer:
            return
        if getattr(self, 'wasPlayingBeforeSeek', False):
            self.mediaPlayer.play()

    def eventFilter(self, obj, event):
        spin_set = getattr(self, "_spinSelectAllOnFocus", set())
        if event.type() in (QEvent.FocusIn, QEvent.MouseButtonPress):
            from PySide6.QtWidgets import QLineEdit, QSpinBox
            if obj in spin_set:
                QTimer.singleShot(0, lambda o=obj: o.lineEdit().selectAll())
            elif isinstance(obj, QLineEdit) and isinstance(obj.parent(), QSpinBox):
                if obj.parent() in spin_set:
                    QTimer.singleShot(0, obj.selectAll)

        if obj is getattr(self.ui, 'videoTimelineSlider', None) and event.type() == QEvent.Type.MouseButtonPress:
            slider = obj
            if self.mediaPlayer and self.videoDuration > 0 and slider.minimum() < slider.maximum():
                opt = QStyleOptionSlider()
                slider.initStyleOption(opt)
                groove = slider.style().subControlRect(
                    QStyle.ComplexControl.CC_Slider, opt,
                    QStyle.SubControl.SC_SliderGroove, slider
                )
                if groove.isValid() and groove.contains(event.pos()):
                    x = event.pos().x() - groove.x()
                    value = slider.minimum() + int((slider.maximum() - slider.minimum()) * x / max(1, groove.width()))
                    value = max(slider.minimum(), min(slider.maximum(), value))
                    slider.setValue(value)
                    self.seekVideo(value)
                    return True
        return super().eventFilter(obj, event)

    def onVideoDurationChanged(self, duration):
        self.videoDuration = duration / 1000.0
        if hasattr(self.ui, 'videoTimelineSlider'):
            self.ui.videoTimelineSlider.setMaximum(1000)
        self.updateVideoTime()
        self._updateTrimSegmentBar()

    def onVideoPositionChanged(self, position):
        if not hasattr(self.ui, 'videoTimelineSlider') or self.videoDuration <= 0:
            return
        if not self.ui.videoTimelineSlider.isSliderDown():
            max_value = self.ui.videoTimelineSlider.maximum()
            slider_position = int((position / 1000.0 / self.videoDuration) * max_value)
            self.ui.videoTimelineSlider.setValue(slider_position)

    def onVideoPlaybackStateChanged(self, state):
        if hasattr(self.ui, 'videoPlayButton'):
            if state == QMediaPlayer.PlayingState:
                self.ui.videoPlayButton.setText("Pause")
            else:
                self.ui.videoPlayButton.setText("Play")

    def updateVideoTime(self):
        if not hasattr(self.ui, 'videoTimeLabel') or not self.mediaPlayer:
            return
        current_pos = self.mediaPlayer.position() / 1000.0
        duration = self.videoDuration
        current_str = self._formatTime(current_pos)
        duration_str = self._formatTime(duration)
        self.ui.videoTimeLabel.setText(f"{current_str} / {duration_str}")

    def _formatTime(self, seconds):
        if seconds < 0:
            seconds = 0
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"
