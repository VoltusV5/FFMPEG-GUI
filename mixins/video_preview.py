"""Миксин: предпросмотр видео, полоска обрезки, таймер времени."""

import logging
from PySide6.QtWidgets import QVBoxLayout, QStyleOptionSlider, QStyle, QLabel
from PySide6.QtCore import Qt, QUrl, QEvent, QTimer
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget as QVideoWidgetBase

from app.constants import FRAME_STEP_MS
from widgets import TrimSegmentBar

logger = logging.getLogger(__name__)


class VideoPreviewMixin:
    """Миксин: инициализация плеера, загрузка видео, seek, trim/keep, полоска обрезки, отображение времени."""

    def initVideoPreview(self):
        """Инициализирует медиаплеер для предпросмотра видео. При отсутствии Qt Multimedia бэкенда показывает заглушку."""
        self.mediaPlayer = None
        self.audioOutput = None
        self.videoWidget = None
        self._previewJustLoaded = False
        self._suppressPlaybackUi = False
        try:
            self.mediaPlayer = QMediaPlayer(self)
            if not self.mediaPlayer.isAvailable():
                # В некоторых средах isAvailable() может давать ложный "false",
                # поэтому не блокируем плеер и продолжаем попытку воспроизведения.
                logger.warning("QMediaPlayer сообщает недоступность бэкенда, продолжаем инициализацию.")
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
            if hasattr(self.mediaPlayer, "errorOccurred"):
                self.mediaPlayer.errorOccurred.connect(self.onVideoPlayerError)
            elif hasattr(self.mediaPlayer, "errorChanged"):
                self.mediaPlayer.errorChanged.connect(self.onVideoPlayerError)

            self.audioOutput.setVolume(1.0)
            self.isMuted = False
            self._setVideoControlsEnabled(True)

            if hasattr(self.ui, 'verticalLayout') and hasattr(self.ui, 'videoTimelineSlider'):
                self.trimSegmentBar = TrimSegmentBar(self.ui.videoTimelineSlider.parent())
                self.ui.verticalLayout.insertWidget(2, self.trimSegmentBar)
                self._updateTrimSegmentBar()
            if hasattr(self.ui, 'videoTimelineSlider'):
                self.ui.videoTimelineSlider.installEventFilter(self)
        except Exception as e:
            logger.warning("Медиаплеер недоступен (нет Qt Multimedia бэкенда): %s", e)
            self.mediaPlayer = None
            self.audioOutput = None
            self.videoWidget = None
            self._showVideoPreviewUnavailable()
        if not hasattr(self, 'trimSegmentBar'):
            self.trimSegmentBar = None

    def _showVideoPreviewUnavailable(self):
        """Показывает заглушку в области предпросмотра, если видеоплеер недоступен."""
        if not hasattr(self.ui, 'videoPreviewWidget'):
            return
        self._setVideoControlsEnabled(False)
        w = self.ui.videoPreviewWidget
        w.setFixedSize(384, 216)
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 8, 8, 8)
        label = QLabel(
            "Видеоплеер недоступен\n(нет мультимедиа-бэкенда).\nПредпросмотр отключён."
        )
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setWordWrap(True)
        label.setStyleSheet("color: #9e9e9e; font-size: 12px;")
        layout.addWidget(label)

    def _setVideoControlsEnabled(self, enabled):
        """Включает/выключает элементы управления предпросмотром."""
        controls = [
            "videoPlayButton", "PreviousFrame", "NextFrame",
            "SetInPoint", "SetOutPoint", "AddKeepArea",
            "videoMuteButton", "videoTimelineSlider",
        ]
        for name in controls:
            if hasattr(self.ui, name):
                getattr(self.ui, name).setEnabled(enabled)

    def _reportVideoPlayerProblem(self, message):
        """Локальное уведомление о проблеме плеера (статусбар + лог)."""
        logger.warning("Video preview: %s", message)
        if hasattr(self, "updateStatus"):
            self.updateStatus(message)

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

    def _applyVideoDurationToUI(self):
        """Обновляет слайдер, метку времени и полоску обрезки по текущей self.videoDuration (в секундах)."""
        if getattr(self, 'videoDuration', 0) <= 0:
            return
        if hasattr(self.ui, 'videoTimelineSlider'):
            self.ui.videoTimelineSlider.setMaximum(1000)
            if self.mediaPlayer and self.mediaPlayer.position() == 0:
                self.ui.videoTimelineSlider.setValue(0)
        self.updateVideoTime()
        self._updateTrimSegmentBar()

    def _getEffectiveDurationSec(self):
        """Возвращает доступную длительность видео (сек), даже если self.videoDuration ещё не задана."""
        if getattr(self, 'videoDuration', 0) > 0:
            return self.videoDuration
        if self.mediaPlayer:
            dur_ms = self.mediaPlayer.duration()
            if dur_ms and dur_ms > 0:
                return dur_ms / 1000.0
        return 0.0

    def _getFrameStepMs(self):
        """Возвращает шаг кадра в миллисекундах с учётом fps из ffprobe."""
        item = self.getSelectedQueueItem()
        fps = getattr(item, "video_fps", 0) if item else 0
        if fps and fps > 0:
            return max(1, int(round(1000.0 / fps)))
        return FRAME_STEP_MS

    def _forceRenderCurrentFrame(self):
        """Принудительно обновляет кадр после seek в паузе (для бэкендов, которые не рисуют кадр при pause)."""
        if not self.mediaPlayer:
            return
        if self.mediaPlayer.playbackState() == QMediaPlayer.PlayingState:
            return
        # Короткий play->pause, чтобы бэкенд перерисовал кадр
        self._setPlaybackUiSuppressed(True)
        self.mediaPlayer.play()
        QTimer.singleShot(30, self.mediaPlayer.pause)
        QTimer.singleShot(60, self._clearPlaybackUiSuppression)

    def _setPlaybackUiSuppressed(self, value):
        self._suppressPlaybackUi = value

    def _clearPlaybackUiSuppression(self):
        self._suppressPlaybackUi = False
        self._refreshPlayButtonLabel()

    def _refreshPlayButtonLabel(self):
        if not hasattr(self.ui, 'videoPlayButton') or not self.mediaPlayer:
            return
        if self.mediaPlayer.playbackState() == QMediaPlayer.PlayingState:
            self.ui.videoPlayButton.setText("Pause")
        else:
            self.ui.videoPlayButton.setText("Play")

    def loadVideoForPreview(self):
        """Загружает видео в медиаплеер для предпросмотра; после загрузки показывается первый кадр."""
        item = self.getSelectedQueueItem()
        if not self.mediaPlayer or not item:
            return
        try:
            self.mediaPlayer.stop()
            url = QUrl.fromLocalFile(item.file_path)
            self.mediaPlayer.setSource(url)
            self._previewJustLoaded = True
            self.inputFile = item.file_path
            # Сразу задаём длительность из ffprobe (элемент очереди), чтобы слайдер и перемотка работали,
            # даже если Qt Multimedia бэкенд не присылает durationChanged
            if getattr(item, 'video_duration', 0) > 0:
                self.videoDuration = item.video_duration
                self._applyVideoDurationToUI()
        except Exception:
            logger.exception("Ошибка загрузки видео")

    def _ensureVideoLoaded(self):
        """Проверяет, что выбран файл и он загружен в плеер."""
        if not self.mediaPlayer:
            self._reportVideoPlayerProblem("Видеоплеер недоступен (нет мультимедиа-бэкенда).")
            return False
        item = self.getSelectedQueueItem()
        if not item:
            self._reportVideoPlayerProblem("Не выбран файл в очереди для предпросмотра.")
            return False
        if self.mediaPlayer.source().isEmpty():
            self.loadVideoForPreview()
        if self.mediaPlayer.source().isEmpty():
            self._reportVideoPlayerProblem("Видео не загружено для предпросмотра.")
            return False
        return True

    def onVideoMediaStatusChanged(self, status):
        """После загрузки медиа показываем первый кадр (позиция 0, пауза)."""
        if status == QMediaPlayer.MediaStatus.LoadedMedia or status == QMediaPlayer.MediaStatus.BufferedMedia:
            if self.mediaPlayer and self._previewJustLoaded:
                self.mediaPlayer.setPosition(0)
                # Не останавливаем воспроизведение, если пользователь уже нажал Play
                if self.mediaPlayer.playbackState() != QMediaPlayer.PlayingState:
                    self.mediaPlayer.pause()
                    if hasattr(self.ui, 'videoPlayButton'):
                        self.ui.videoPlayButton.setText("Play")
            self._previewJustLoaded = False
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            self._reportVideoPlayerProblem("Видео не может быть воспроизведено этим бэкендом.")

    def toggleVideoPlayback(self):
        if not self._ensureVideoLoaded():
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
        if not self._ensureVideoLoaded():
            return
        step_ms = self._getFrameStepMs()
        pos_ms = self.mediaPlayer.position()
        self.mediaPlayer.setPosition(max(0, pos_ms - step_ms))
        self._forceRenderCurrentFrame()

    def stepVideoNextFrame(self):
        if not self._ensureVideoLoaded():
            return
        step_ms = self._getFrameStepMs()
        pos_ms = self.mediaPlayer.position()
        duration_sec = self._getEffectiveDurationSec()
        if duration_sec > 0:
            duration_ms = int(duration_sec * 1000)
            self.mediaPlayer.setPosition(min(duration_ms, pos_ms + step_ms))
        else:
            self.mediaPlayer.setPosition(pos_ms + step_ms)
        self._forceRenderCurrentFrame()

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
        if not self._ensureVideoLoaded():
            return
        duration_sec = self._getEffectiveDurationSec()
        if duration_sec <= 0:
            return
        max_value = self.ui.videoTimelineSlider.maximum()
        if max_value <= 0:
            return
        time_ms = int((position / max_value) * duration_sec * 1000)
        self.mediaPlayer.setPosition(time_ms)
        self._forceRenderCurrentFrame()

    def onVideoTimelineValueChanged(self, value):
        """Вызывается при valueChanged слайдера: перемотка только если пользователь сам двигал слайдер (клик или перетаскивание)."""
        if hasattr(self.ui, 'videoTimelineSlider') and self.ui.videoTimelineSlider.isSliderDown():
            self.seekVideo(value)

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
            if self.mediaPlayer and self._getEffectiveDurationSec() > 0 and slider.minimum() < slider.maximum():
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
        # Обновляем длительность только если плеер её сообщил (> 0), иначе сохраняем значение из ffprobe (item.video_duration)
        if duration and duration > 0:
            self.videoDuration = duration / 1000.0
        self._applyVideoDurationToUI()

    def onVideoPositionChanged(self, position):
        if not hasattr(self.ui, 'videoTimelineSlider'):
            return
        duration_sec = self._getEffectiveDurationSec()
        if duration_sec <= 0:
            return
        if not self.ui.videoTimelineSlider.isSliderDown():
            max_value = self.ui.videoTimelineSlider.maximum()
            slider_position = int((position / 1000.0 / duration_sec) * max_value)
            self.ui.videoTimelineSlider.setValue(slider_position)

    def onVideoPlaybackStateChanged(self, state):
        if self._suppressPlaybackUi:
            return
        self._refreshPlayButtonLabel()

    def updateVideoTime(self):
        if not hasattr(self.ui, 'videoTimeLabel') or not self.mediaPlayer:
            return
        current_pos = self.mediaPlayer.position() / 1000.0
        duration = self._getEffectiveDurationSec()
        if self.videoDuration <= 0 and duration > 0:
            self.videoDuration = duration
        current_str = self._formatTime(current_pos)
        duration_str = self._formatTime(duration)
        self.ui.videoTimeLabel.setText(f"{current_str} / {duration_str}")

    def onVideoPlayerError(self, *args):
        """Отображает ошибку медиаплеера, если бэкенд не смог воспроизвести файл."""
        if not self.mediaPlayer:
            return
        msg = self.mediaPlayer.errorString() if hasattr(self.mediaPlayer, "errorString") else ""
        msg = msg or "Ошибка воспроизведения."
        self._reportVideoPlayerProblem(msg)

    def _formatTime(self, seconds):
        if seconds < 0:
            seconds = 0
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"
