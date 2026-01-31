import sys
import os
import platform
import shlex
import re
import json
import shutil
from PySide6.QtWidgets import (QMainWindow, QFileDialog, QMessageBox, QInputDialog, 
                               QVBoxLayout, QTableWidgetItem, QProgressBar, QPushButton,
                               QHeaderView, QAbstractItemView, QButtonGroup, QWidget,
                               QStyleOptionSlider, QStyle, QMenu, QHBoxLayout, QLabel,
                               QSpinBox, QComboBox, QCheckBox, QLineEdit, QScrollArea, QFrame,
                               QGridLayout)
from PySide6.QtCore import QProcess, QUrl, Qt, QTimer, QMimeData, QRectF, QEvent
from PySide6.QtGui import QGuiApplication, QDragEnterEvent, QDropEvent, QPainter, QColor, QBrush, QFont
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from ui_mainwindow import Ui_MainWindow  # Сгенерированный из .ui интерфейс
from presetmanager import PresetManager
from queueitem import QueueItem


class TrimSegmentBar(QWidget):
    """Полоска под слайдером: подсвечивает области обрезки (зелёный — добавленные, синий — текущий in–out)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(14)
        self.setMinimumWidth(100)
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
        radius = min(4, h // 2)
        painter.setPen(Qt.PenStyle.NoPen)
        # Фон — тёмно-серая полоска под тему
        painter.fillRect(0, 0, w, h, QColor(0x40, 0x40, 0x40))
        # Добавленные области склейки — приглушённый зелёный, скруглённые края
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
                painter.setBrush(QColor(56, 142, 60))
                painter.drawRoundedRect(QRectF(x1, 0, seg_w, h), r, r)
        # Текущий промежуток in–out — акцентный синий, скруглённые края
        if self.trim_start_sec is not None and self.trim_end_sec is not None and self.trim_end_sec > self.trim_start_sec:
            x1 = int(w * self.trim_start_sec / self.duration_sec)
            x2 = int(w * self.trim_end_sec / self.duration_sec)
            x1 = max(0, min(x1, w))
            x2 = max(0, min(x2, w))
            if x2 > x1:
                seg_w = x2 - x1
                r = min(radius, seg_w // 2, h // 2)
                painter.setBrush(QColor(0x4a, 0x9e, 0xff))
                painter.drawRoundedRect(QRectF(x1, 0, seg_w, h), r, r)
        painter.end()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle("OpenFF GUI - MVP")
        self.resize(1425, 900)
        # Переопределяем стили под тёмную тему (ui_mainwindow генерируется из .ui)
        if hasattr(self.ui, 'runButton'):
            self.ui.runButton.setStyleSheet(
                "background-color: #2e7d32; color: white; font-weight: bold; padding: 8px; border: 1px solid #1b5e20;"
            )
        if hasattr(self.ui, 'videoPreviewWidget'):
            self.ui.videoPreviewWidget.setStyleSheet("border: 1px solid #505050; background-color: #000000;")
        if hasattr(self.ui, 'commandDisplay'):
            self.ui.commandDisplay.setStyleSheet(
                "background-color: #3c3c3c; color: #e0e0e0; font-family: Consolas, monospace; border: 1px solid #505050;"
            )
        if hasattr(self.ui, 'SetInPoint'):
            self.ui.SetInPoint.setText("[")
        if hasattr(self.ui, 'SetOutPoint'):
            self.ui.SetOutPoint.setText("]")
        if hasattr(self.ui, 'PreviousFrame'):
            self.ui.PreviousFrame.setText("\u2190")   # ← предыдущий кадр
        if hasattr(self.ui, 'NextFrame'):
            self.ui.NextFrame.setText("\u2192")      # → следующий кадр
        # Размер кнопок под видеоплеером: по умолчанию — как в теме (main.py QPushButton).
        # Чтобы снова сделать их меньше, раскомментируйте блок ниже (или меняйте значения здесь):
        # if hasattr(self.ui, 'videoControlsLayout'):
        #     for i in range(self.ui.videoControlsLayout.count()):
        #         w = self.ui.videoControlsLayout.itemAt(i).widget()
        #         if w is not None and isinstance(w, QPushButton):
        #             w.setMaximumHeight(22)
        #             w.setStyleSheet("padding: 1px 4px; min-height: 0;")
        # Альтернатива: в Qt Designer (mainwindow.ui) — виджет videoPreviewContainer,
        # или кнопки в verticalLayoutWidget_2 (videoPlayButton, PreviousFrame и т.д.) — свойство maximumSize.
        # Высота блока «Настройка пресетов» (таблица пресетов). Менять здесь или в mainwindow.ui:
        if hasattr(self.ui, 'presetEditorContainer'):
            self.ui.presetEditorContainer.setFixedHeight(311)   # было 231, +70 px
        if hasattr(self.ui, 'verticalLayoutWidget_3'):
            self.ui.verticalLayoutWidget_3.setFixedHeight(298)  # было 221, +70 px
        if hasattr(self.ui, 'createPresetButton'):
            self.ui.createPresetButton.setMaximumHeight(28)
            self.ui.createPresetButton.setStyleSheet("padding: 4px 10px;")
        if hasattr(self.ui, 'savePresetChangesButton'):
            self.ui.savePresetChangesButton.setMaximumHeight(28)
            self.ui.savePresetChangesButton.setStyleSheet("padding: 4px 10px;")
        for attr in ("savePresetWithCustomParamsButton", "savePresetCustomParamsButton", "savePresetWithExtraParamsButton"):
            btn = getattr(self.ui, attr, None)
            if btn is not None:
                btn.setMaximumHeight(28)
                btn.setStyleSheet("padding: 4px 10px;")

        self.ffmpegProcess = QProcess(self)
        self.presetManager = PresetManager()
        self.currentPresetName = None  # Текущий редактируемый пресет
        # Пользовательские опции (контейнеры, кодеки, разрешения, аудио-кодеки) — сохраняются между запусками
        self.customContainers = []
        self.customCodecs = []
        self.customResolutions = []
        self.customAudioCodecs = []
        self._customOptionsPath = os.path.join(os.path.dirname(__file__), "custom_options.json")
        self._savedCommandsPath = os.path.join(os.path.dirname(__file__), "saved_commands.json")
        self._loadCustomOptions()
        self.currentCodecCustom = ""   # Кастомный кодек для редактора пресетов
        self.currentContainerCustom = ""  # Кастомный контейнер
        self.currentResolutionCustom = "" # Кастомное разрешение
        self.currentAudioCodecCustom = ""  # Кастомный аудио-кодек
        
        # Очередь файлов
        self.queue = []  # Список QueueItem
        self.currentQueueIndex = -1  # Индекс текущего обрабатываемого файла
        self.selectedQueueIndex = -1  # Индекс выделенного файла в таблице
        
        # Переменные для текущего файла (для обратной совместимости)
        self.inputFile = ""
        self.lastOutputFile = ""
        # Глобальные флаги оставляем для совместимости, но основное
        # состояние команды теперь хранится внутри каждого QueueItem
        self.commandManuallyEdited = False
        self.lastGeneratedCommand = ""
        self._spinSelectAllOnFocus = set()
        self._warningLabel = None
        self._conflictStyles = {}
        self._extraLabel = None
        self._queueProgressTarget = None
        self._queueProgressMaxValue = 0
        self._queueProgressTimer = QTimer(self)
        self._queueProgressTimer.timeout.connect(self._tickQueueProgress)
        self._suppressPresetEditorUpdates = False
        
        # Переменные для прогресса кодирования
        self.encodingProgress = 0
        self.totalFrames = 0
        self.currentFrame = 0
        self.videoDuration = 0
        self.encodingDuration = 0
        self.isPaused = False

        # Переменные для общего прогресса очереди
        self.totalQueueProgress = 0

        # Флаги управления остановкой очереди через кнопку "Пауза"
        # (по ТЗ: пауза = отменить текущий файл и все следующие, затем возобновить с текущего)
        self._pauseStopRequested = False
        self.pausedQueueIndex = -1
        
        # Инициализация медиаплеера для предпросмотра
        self.initVideoPreview()
        
        # Инициализация очереди
        self.initQueue()

        # Инициализация редактора пресетов (новый UI)
        self.initPresetEditor()
        # Настройки пресетов видны сразу, не зависят от выбора файла в очереди
        if hasattr(self.ui, 'presetEditorContainer'):
            self.ui.presetEditorContainer.show()

        # Выделять весь текст при фокусе у всех QSpinBox
        for spin in self.findChildren(QSpinBox):
            self._spinSelectAllOnFocus.add(spin)
            spin.installEventFilter(self)
            try:
                spin.lineEdit().installEventFilter(self)
            except Exception:
                pass

        # Более тёмная область выпадающего списка для всех QComboBox
        combo_style = (
            "QComboBox::drop-down {"
            "  background-color: #2f2f2f;"
            "  border-left: 1px solid #505050;"
            "  width: 18px;"
            "}"
        )
        for combo in self.findChildren(QComboBox):
            combo.setStyleSheet(combo_style)

        # Подложка таблиц и номера строк — серый фон (как основная подложка)
        for tbl in [getattr(self.ui, "queueTableWidget", None), getattr(self.ui, "presetsTableWidget", None)]:
            if tbl is not None:
                tbl.verticalHeader().setStyleSheet(
                    "background-color: #363636; color: #e0e0e0; border: none; border-right: 1px solid #505050;"
                )
        # Подключение сигналов
        # Кнопки очереди
        if hasattr(self.ui, 'addFilesButton'):
            self.ui.addFilesButton.clicked.connect(self.addFilesToQueue)
        if hasattr(self.ui, 'removeFromQueueButton'):
            self.ui.removeFromQueueButton.clicked.connect(self.removeSelectedFromQueue)
        if hasattr(self.ui, 'QueueUp'):
            self.ui.QueueUp.clicked.connect(self.moveQueueItemUp)
        if hasattr(self.ui, 'QueueDown'):
            self.ui.QueueDown.clicked.connect(self.moveQueueItemDown)
        
        # Кнопки управления (работают для выделенного файла)
        if hasattr(self.ui, 'commandDisplay'):
            self.ui.commandDisplay.textChanged.connect(self.onCommandManuallyEdited)
        if hasattr(self.ui, 'runButton'):
            self.ui.runButton.clicked.connect(self.startQueueProcessing)
        if hasattr(self.ui, 'copyCmdButton'):
            self.ui.copyCmdButton.clicked.connect(self.copyCommand)
            self.ui.copyCmdButton.setToolTip("Копировать текущую команду FFmpeg в буфер обмена.")
        if hasattr(self.ui, 'saveCurrentCommand'):
            self.ui.saveCurrentCommand.clicked.connect(self.saveCurrentCommand)
            self.ui.saveCurrentCommand.setToolTip("Сохранить текущую команду FFmpeg как шаблон.")
        if hasattr(self.ui, 'loadSavedCommand'):
            self.ui.loadSavedCommand.clicked.connect(self.loadSavedCommand)
            self.ui.loadSavedCommand.setToolTip("Загрузить сохранённую команду и применить к выбранному файлу.")
        if hasattr(self.ui, 'deleteSavedCommand'):
            self.ui.deleteSavedCommand.clicked.connect(self.deleteSavedCommand)
            self.ui.deleteSavedCommand.setToolTip("Удалить сохранённую команду из списка.")
        if hasattr(self.ui, 'openOutputFolderButton'):
            self.ui.openOutputFolderButton.clicked.connect(self.openOutputFolder)
            self.ui.openOutputFolderButton.setToolTip("Открыть папку с последним выходным файлом.")

        # Кнопки редактора пресетов (новый UI)
        if hasattr(self.ui, 'presetExportButton'):
            self.ui.presetExportButton.clicked.connect(self.exportData)
        if hasattr(self.ui, 'presetImportButton'):
            self.ui.presetImportButton.clicked.connect(self.importData)
        if hasattr(self.ui, 'createPresetButton'):
            self.ui.createPresetButton.clicked.connect(self.createPreset)
        if hasattr(self.ui, 'savePresetChangesButton'):
            self.ui.savePresetChangesButton.clicked.connect(self.saveCurrentPreset)
        if hasattr(self.ui, 'PresetUp'):
            self.ui.PresetUp.clicked.connect(self.movePresetUp)
        if hasattr(self.ui, 'PresetDown'):
            self.ui.PresetDown.clicked.connect(self.movePresetDown)
        # Кнопка сохранения пресета с пользовательскими доп. параметрами
        for attr in ("savePresetWithCustomParamsButton", "savePresetCustomParamsButton", "savePresetWithExtraParamsButton"):
            btn = getattr(self.ui, attr, None)
            if btn is not None:
                btn.clicked.connect(self.savePresetWithCustomParams)
                btn.setToolTip("Сохраняет пресет вместе с дополнительными параметрами,\n"
                               "которые вы вручную дописали в команду FFmpeg.")

        # Лог выполнения всегда включён; кнопка «Показать лог» убрана
        if hasattr(self.ui, 'showFFmpegLogButton'):
            self.ui.showFFmpegLogButton.hide()

        # Подключение кнопок предпросмотра (если они существуют)
        if hasattr(self.ui, 'videoPlayButton'):
            self.ui.videoPlayButton.clicked.connect(self.toggleVideoPlayback)
        if hasattr(self.ui, 'PreviousFrame'):
            self.ui.PreviousFrame.clicked.connect(self.stepVideoPreviousFrame)
        if hasattr(self.ui, 'NextFrame'):
            self.ui.NextFrame.clicked.connect(self.stepVideoNextFrame)
        if hasattr(self.ui, 'SetInPoint'):
            self.ui.SetInPoint.clicked.connect(self.setTrimStart)   # In = начало оставляемого промежутка
        if hasattr(self.ui, 'SetOutPoint'):
            self.ui.SetOutPoint.clicked.connect(self.setTrimEnd)   # Out = конец оставляемого промежутка
        if hasattr(self.ui, 'AddKeepArea'):
            self.ui.AddKeepArea.clicked.connect(self.addKeepArea)
        if hasattr(self.ui, 'videoMuteButton'):
            self.ui.videoMuteButton.clicked.connect(self.toggleVideoMute)
        if hasattr(self.ui, 'videoTimelineSlider'):
            self.ui.videoTimelineSlider.sliderMoved.connect(self.seekVideo)
            self.ui.videoTimelineSlider.sliderPressed.connect(self.pauseVideoForSeek)
            self.ui.videoTimelineSlider.sliderReleased.connect(self.resumeVideoAfterSeek)
        self._setVideoPlayerTooltips()
        
        # Подключение кнопки паузы
        if hasattr(self.ui, 'pauseResumeButton'):
            self.ui.pauseResumeButton.clicked.connect(self.togglePauseEncoding)

        self.ffmpegProcess.readyReadStandardOutput.connect(self.readProcessOutput)
        self.ffmpegProcess.readyReadStandardError.connect(self.readProcessOutput)
        self.ffmpegProcess.finished.connect(self.processFinished)
        
        # Таймер для обновления времени видео
        self.videoUpdateTimer = QTimer(self)
        self.videoUpdateTimer.timeout.connect(self.updateVideoTime)
        self.videoUpdateTimer.start(100)  # Обновление каждые 100мс
        
        # Инициализация статуса
        self.updateStatus("Готов")

        # Лог выполнения всегда виден (кнопка отключена)
        self.isLogVisible = True

    def initQueue(self):
        """Инициализирует таблицу очереди"""
        if not hasattr(self.ui, 'queueTableWidget'):
            return
        
        # Настраиваем таблицу
        table = self.ui.queueTableWidget
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels([
            "Входной файл", "Выходной файл", "Пресет", "Статус", "Прогресс", "Открыть"
        ])
        
        # Разрешаем множественное выделение строк (для массового применения пресетов)
        table.setSelectionMode(QAbstractItemView.ExtendedSelection)

        # Настройка столбцов (ширины не меняются при выборе файла)
        self._applyQueueTableColumnWidths()

        # Настройка drag-and-drop
        table.setAcceptDrops(True)
        table.setDragDropMode(QAbstractItemView.DropOnly)
        table.setDefaultDropAction(Qt.CopyAction)
        
        # Подключаем сигналы
        table.itemSelectionChanged.connect(self.onQueueItemSelected)
        table.cellDoubleClicked.connect(self.onQueueCellDoubleClicked)
        table.itemChanged.connect(self.onQueueItemChanged)
        
        # Включаем drag-and-drop
        table.setAcceptDrops(True)
        
        # Переопределяем методы drag-and-drop (через переопределение класса таблицы)
        # Это будет сделано через установку обработчиков событий
        self.setupDragAndDrop()

    def _applyQueueTableColumnWidths(self):
        """Ширины колонок таблицы очереди: при пустой таблице — без нумерации и без пустого места справа; при наличии строк — нумерация за счёт колонок Входной/Выходной файл."""
        if not hasattr(self.ui, 'queueTableWidget'):
            return
        table = self.ui.queueTableWidget
        header = table.horizontalHeader()
        header.setStretchLastSection(False)
        has_rows = table.rowCount() > 0
        if has_rows:
            table.verticalHeader().setVisible(True)
            # Колонки 0 и 1 уменьшены на 15 px каждая под нумерацию строк
            widths = (200, 200, 80, 100, 80, 78)
        else:
            table.verticalHeader().setVisible(False)
            # Полная ширина колонок — нет пустого места справа
            widths = (215, 215, 80, 100, 80, 78)
        for col, w in enumerate(widths):
            header.setSectionResizeMode(col, QHeaderView.Fixed)
            table.setColumnWidth(col, w)

    # ===== Инициализация и логика редактора пресетов (новый UI) =====

    def _loadCustomOptions(self):
        """Загружает списки пользовательских опций (контейнеры, кодеки, разрешения, аудио-кодеки) из custom_options.json."""
        if not os.path.exists(self._customOptionsPath):
            return
        try:
            with open(self._customOptionsPath, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.customContainers = data.get("containers", [])
            if not isinstance(self.customContainers, list):
                self.customContainers = []
            self.customCodecs = data.get("codecs", [])
            if not isinstance(self.customCodecs, list):
                self.customCodecs = []
            self.customResolutions = data.get("resolutions", [])
            if not isinstance(self.customResolutions, list):
                self.customResolutions = []
            self.customAudioCodecs = data.get("audio_codecs", [])
            if not isinstance(self.customAudioCodecs, list):
                self.customAudioCodecs = []
        except Exception:
            self.customContainers = []
            self.customCodecs = []
            self.customResolutions = []
            self.customAudioCodecs = []

    def _saveCustomOptions(self):
        """Сохраняет списки пользовательских опций в custom_options.json."""
        try:
            data = {
                "containers": getattr(self, "customContainers", []),
                "codecs": getattr(self, "customCodecs", []),
                "resolutions": getattr(self, "customResolutions", []),
                "audio_codecs": getattr(self, "customAudioCodecs", []),
            }
            with open(self._customOptionsPath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения custom_options: {e}")

    def _loadSavedCommands(self):
        """Загружает список сохранённых команд из saved_commands.json. Возвращает список dict с ключами name, command."""
        if not os.path.exists(self._savedCommandsPath):
            return []
        try:
            with open(self._savedCommandsPath, "r", encoding="utf-8") as f:
                data = json.load(f)
            lst = data.get("commands", [])
            if not isinstance(lst, list):
                return []
            return [x for x in lst if isinstance(x, dict) and x.get("name") and x.get("command") is not None]
        except Exception:
            return []

    def _saveSavedCommands(self, commands_list):
        """Сохраняет список сохранённых команд в saved_commands.json. commands_list — список dict с ключами name, command."""
        try:
            data = {"commands": commands_list}
            with open(self._savedCommandsPath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения saved_commands: {e}")

    def _showCustomContainerMenu(self):
        """Показывает выпадающее меню: сохранённые контейнеры + «Добавить»."""
        btn = getattr(self.ui, "containerCustomButton", None)
        if btn is None:
            return
        menu = QMenu(self)
        current = (self.currentContainerCustom or "").lower()
        for name in self.customContainers:
            if not name or not isinstance(name, str):
                continue
            action = menu.addAction(name)
            action.setCheckable(True)
            if name.lower() == current:
                action.setChecked(True)
            action.triggered.connect(lambda checked=False, n=name: self._onCustomContainerSelected(n))
        menu.addSeparator()
        add_action = menu.addAction("Добавить…")
        add_action.triggered.connect(self._onAddCustomContainer)
        delete_action = menu.addAction("Удалить…")
        delete_action.triggered.connect(self._onDeleteCustomContainer)
        menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))

    def _onCustomContainerSelected(self, name):
        """Выбран пункт из списка пользовательских контейнеров."""
        self.currentContainerCustom = name
        if hasattr(self.ui, "containerCustomButton"):
            self.ui.containerCustomButton.setChecked(True)
        self.updateCommandFromPresetEditor()

    def _onAddCustomContainer(self):
        """Добавить новый контейнер через диалог."""
        text, ok = QInputDialog.getText(
            self,
            "Пользовательский контейнер",
            "Введите расширение контейнера (например, mov):",
            text=self.currentContainerCustom or "mp4"
        )
        if ok and text.strip():
            name = text.strip().lstrip(".").lower()
            if name and name not in self.customContainers:
                self.customContainers.append(name)
                self._saveCustomOptions()
            self.currentContainerCustom = name
            if hasattr(self.ui, "containerCustomButton"):
                self.ui.containerCustomButton.setChecked(True)
            self.updateCommandFromPresetEditor()

    def _onDeleteCustomContainer(self):
        """Удалить контейнер из списка custom."""
        if not self.customContainers:
            QMessageBox.information(self, "Контейнеры", "Нет пользовательских контейнеров.")
            return
        name, ok = QInputDialog.getItem(self, "Удалить контейнер", "Выберите контейнер:", self.customContainers, 0, False)
        if not ok or not name:
            return
        self.customContainers = [c for c in self.customContainers if c != name]
        self._saveCustomOptions()
        if self.currentContainerCustom == name:
            self.currentContainerCustom = ""
            if hasattr(self.ui, "containerCurrentButton"):
                self.ui.containerCurrentButton.setChecked(True)
        self.updateCommandFromPresetEditor()

    def _showCustomCodecMenu(self):
        """Выпадающее меню: сохранённые кодеки + «Добавить»."""
        btn = getattr(self.ui, "codecCustomButton", None)
        if btn is None:
            return
        menu = QMenu(self)
        current = (self.currentCodecCustom or "").lower()
        for name in getattr(self, "customCodecs", []):
            if not name or not isinstance(name, str):
                continue
            action = menu.addAction(name)
            action.setCheckable(True)
            if name.lower() == current:
                action.setChecked(True)
            action.triggered.connect(lambda checked=False, n=name: self._onCustomCodecSelected(n))
        menu.addSeparator()
        add_action = menu.addAction("Добавить…")
        add_action.triggered.connect(self._onAddCustomCodec)
        delete_action = menu.addAction("Удалить…")
        delete_action.triggered.connect(self._onDeleteCustomCodec)
        menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))

    def _onCustomCodecSelected(self, name):
        self.currentCodecCustom = name
        if hasattr(self.ui, "codecCustomButton"):
            self.ui.codecCustomButton.setChecked(True)
        self.updateCommandFromPresetEditor()

    def _onAddCustomCodec(self):
        text, ok = QInputDialog.getText(
            self, "Пользовательский кодек", "Введите имя видеокодека (например, libx264):",
            text=self.currentCodecCustom or "libx264"
        )
        if ok and text.strip():
            name = text.strip()
            if name not in self.customCodecs:
                self.customCodecs.append(name)
                self._saveCustomOptions()
            self.currentCodecCustom = name
            if hasattr(self.ui, "codecCustomButton"):
                self.ui.codecCustomButton.setChecked(True)
            self.updateCommandFromPresetEditor()

    def _onDeleteCustomCodec(self):
        if not self.customCodecs:
            QMessageBox.information(self, "Кодеки", "Нет пользовательских кодеков.")
            return
        name, ok = QInputDialog.getItem(self, "Удалить кодек", "Выберите кодек:", self.customCodecs, 0, False)
        if not ok or not name:
            return
        self.customCodecs = [c for c in self.customCodecs if c != name]
        self._saveCustomOptions()
        if self.currentCodecCustom == name:
            self.currentCodecCustom = ""
            if hasattr(self.ui, "codecCurrentButton"):
                self.ui.codecCurrentButton.setChecked(True)
        self.updateCommandFromPresetEditor()

    def _showCustomResolutionMenu(self):
        """Выпадающее меню: сохранённые разрешения + «Добавить»."""
        btn = getattr(self.ui, "resolutionCustomButton", None)
        if btn is None:
            return
        menu = QMenu(self)
        current = (self.currentResolutionCustom or "").replace(" ", "")
        for name in getattr(self, "customResolutions", []):
            if not name or not isinstance(name, str):
                continue
            norm = name.replace(" ", "")
            action = menu.addAction(name)
            action.setCheckable(True)
            if norm == current or norm == current.replace(":", "x"):
                action.setChecked(True)
            action.triggered.connect(lambda checked=False, n=name: self._onCustomResolutionSelected(n))
        menu.addSeparator()
        add_action = menu.addAction("Добавить…")
        add_action.triggered.connect(self._onAddCustomResolution)
        delete_action = menu.addAction("Удалить…")
        delete_action.triggered.connect(self._onDeleteCustomResolution)
        menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))

    def _onCustomResolutionSelected(self, name):
        self.currentResolutionCustom = name.strip().replace("x", ":").replace(" ", "")
        if hasattr(self.ui, "resolutionCustomButton"):
            self.ui.resolutionCustomButton.setChecked(True)
        self.updateCommandFromPresetEditor()

    def _onAddCustomResolution(self):
        text, ok = QInputDialog.getText(
            self, "Пользовательское разрешение", "Введите разрешение (например, 1920:1080 или 1920x1080):",
            text=self.currentResolutionCustom or "1920:1080"
        )
        if ok and text.strip():
            name = text.strip().replace("x", ":").replace(" ", "")
            if name not in self.customResolutions:
                self.customResolutions.append(name)
                self._saveCustomOptions()
            self.currentResolutionCustom = name
            if hasattr(self.ui, "resolutionCustomButton"):
                self.ui.resolutionCustomButton.setChecked(True)
            self.updateCommandFromPresetEditor()

    def _onDeleteCustomResolution(self):
        if not self.customResolutions:
            QMessageBox.information(self, "Разрешения", "Нет пользовательских разрешений.")
            return
        name, ok = QInputDialog.getItem(self, "Удалить разрешение", "Выберите разрешение:", self.customResolutions, 0, False)
        if not ok or not name:
            return
        self.customResolutions = [r for r in self.customResolutions if r != name]
        self._saveCustomOptions()
        if self.currentResolutionCustom.replace("x", ":") == name.replace("x", ":"):
            self.currentResolutionCustom = ""
            if hasattr(self.ui, "resolutionCurrentButton"):
                self.ui.resolutionCurrentButton.setChecked(True)
        self.updateCommandFromPresetEditor()

    def _showCustomAudioCodecMenu(self):
        """Выпадающее меню: сохранённые аудио-кодеки + «Добавить»."""
        btn = getattr(self, "_audioCodecCustomButton", None)
        if btn is None:
            return
        menu = QMenu(self)
        current = (self.currentAudioCodecCustom or "").lower()
        for name in getattr(self, "customAudioCodecs", []):
            if not name or not isinstance(name, str):
                continue
            action = menu.addAction(name)
            action.setCheckable(True)
            if name.lower() == current:
                action.setChecked(True)
            action.triggered.connect(lambda checked=False, n=name: self._onCustomAudioCodecSelected(n))
        menu.addSeparator()
        add_action = menu.addAction("Добавить…")
        add_action.triggered.connect(self._onAddCustomAudioCodec)
        delete_action = menu.addAction("Удалить…")
        delete_action.triggered.connect(self._onDeleteCustomAudioCodec)
        menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))

    def _onCustomAudioCodecSelected(self, name):
        self.currentAudioCodecCustom = name
        if hasattr(self, "_audioCodecCustomButton"):
            self._audioCodecCustomButton.setChecked(True)
        self.updateCommandFromPresetEditor()

    def _onAddCustomAudioCodec(self):
        text, ok = QInputDialog.getText(
            self, "Пользовательский аудио-кодек", "Введите имя аудио-кодека (например, aac, libopus):",
            text=self.currentAudioCodecCustom or "aac"
        )
        if ok and text.strip():
            name = text.strip()
            if name not in self.customAudioCodecs:
                self.customAudioCodecs.append(name)
                self._saveCustomOptions()
            self.currentAudioCodecCustom = name
            if hasattr(self, "_audioCodecCustomButton"):
                self._audioCodecCustomButton.setChecked(True)
            self.updateCommandFromPresetEditor()

    def _onDeleteCustomAudioCodec(self):
        if not self.customAudioCodecs:
            QMessageBox.information(self, "Аудио‑кодеки", "Нет пользовательских аудио‑кодеков.")
            return
        name, ok = QInputDialog.getItem(self, "Удалить аудио‑кодек", "Выберите аудио‑кодек:", self.customAudioCodecs, 0, False)
        if not ok or not name:
            return
        self.customAudioCodecs = [c for c in self.customAudioCodecs if c != name]
        self._saveCustomOptions()
        if self.currentAudioCodecCustom == name:
            self.currentAudioCodecCustom = ""
            if hasattr(self, "_audioCodecCurrentButton"):
                self._audioCodecCurrentButton.setChecked(True)
        self.updateCommandFromPresetEditor()

    def initPresetEditor(self):
        """Настраивает таблицу пресетов и группы кнопок codec/container/resolution."""
        # Если нужных виджетов нет в UI, просто выходим
        if not hasattr(self.ui, 'presetsTableWidget'):
            return

        # Таблица пресетов
        table = self.ui.presetsTableWidget
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels([
            "Название", "Описание",
            "Удалить", "Применить"
        ])
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        # Фиксированные ширины колонок таблицы пресетов.
        # Ширину колонки «Описание» меняйте здесь (строка с setColumnWidth(1, ...)):
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Fixed)
        table.setColumnWidth(0, 125)
        table.setColumnWidth(1, 260)  # Описание: 175 + 10 px
        table.setColumnWidth(2, 70)   # Удалить
        table.setColumnWidth(3, 88)   # Применить

        # Группа кнопок для видеокодека (добавляем prores перед custom)
        self.codecButtonGroup = QButtonGroup(self)
        self.codecButtonGroup.setExclusive(True)
        for attr in ['codecCurrentButton', 'codecLibx264Button', 'codecLibx265Button', 'codecCustomButton']:
            if hasattr(self.ui, attr):
                btn = getattr(self.ui, attr)
                btn.setCheckable(True)
                self.codecButtonGroup.addButton(btn)
        codec_idx = self.ui.codecRowLayout.indexOf(self.ui.codecCustomButton)
        for name, text in [("Prores", "prores")]:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setObjectName(f"codec{name}Button")
            self.ui.codecRowLayout.insertWidget(codec_idx, btn)
            self.codecButtonGroup.addButton(btn)
            setattr(self, f"_codec{name}Button", btn)
            codec_idx += 1
        if hasattr(self, 'codecButtonGroup'):
            self.codecButtonGroup.buttonClicked.connect(self.onCodecButtonClicked)

        # Группа кнопок для контейнера (добавляем mov, avi, mxf перед custom)
        self.containerButtonGroup = QButtonGroup(self)
        self.containerButtonGroup.setExclusive(True)
        for attr in ['containerCurrentButton', 'containerMp4Button', 'containerMkvButton', 'containerCustomButton']:
            if hasattr(self.ui, attr):
                btn = getattr(self.ui, attr)
                btn.setCheckable(True)
                self.containerButtonGroup.addButton(btn)
        idx = self.ui.containerRowLayout.indexOf(self.ui.containerCustomButton)
        for name, text in [("Mov", "mov"), ("Avi", "avi"), ("Mxf", "mxf")]:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setObjectName(f"container{name}Button")
            self.ui.containerRowLayout.insertWidget(idx, btn)
            self.containerButtonGroup.addButton(btn)
            setattr(self, f"_container{name}Button", btn)
            idx += 1
        if hasattr(self, 'containerButtonGroup'):
            self.containerButtonGroup.buttonClicked.connect(self.onContainerButtonClicked)

        # Группа кнопок для разрешения (добавляем 2k, 4k перед custom)
        self.resolutionButtonGroup = QButtonGroup(self)
        self.resolutionButtonGroup.setExclusive(True)
        for attr in ['resolutionCurrentButton', 'resolution480pButton',
                     'resolution720pButton', 'resolution1080pButton',
                     'resolutionCustomButton']:
            if hasattr(self.ui, attr):
                btn = getattr(self.ui, attr)
                btn.setCheckable(True)
                self.resolutionButtonGroup.addButton(btn)
        res_idx = self.ui.resolutionRowLayout.indexOf(self.ui.resolutionCustomButton)
        for name, text in [("2k", "2k"), ("4k", "4k")]:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setObjectName(f"resolution{name.upper()}Button")
            self.ui.resolutionRowLayout.insertWidget(res_idx, btn)
            self.resolutionButtonGroup.addButton(btn)
            setattr(self, f"_resolution{name}Button", btn)
            res_idx += 1
        if hasattr(self, 'resolutionButtonGroup'):
            self.resolutionButtonGroup.buttonClicked.connect(self.onResolutionButtonClicked)

        # Аудио-кодеки: current в начале и по умолчанию, затем aac, mp3, pcm_s16le, pcm_s24le, custom
        self.audioCodecButtonGroup = QButtonGroup(self)
        self.audioCodecButtonGroup.setExclusive(True)
        audio_row = QHBoxLayout()
        audio_row.setSpacing(5)
        audio_row.addWidget(QLabel("Аудио-кодеки:"))
        for name, text in [("Current", "current"), ("Aac", "aac"), ("Mp3", "mp3"), ("Pcm16", "pcm_s16le"), ("Pcm24", "pcm_s24le"), ("Custom", "custom")]:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setObjectName(f"audioCodec{name}Button")
            audio_row.addWidget(btn)
            self.audioCodecButtonGroup.addButton(btn)
            setattr(self, f"_audioCodec{name}Button", btn)
        self._audioCodecCurrentButton.setChecked(True)
        self.ui.presetSettingsLayout.addLayout(audio_row)
        self.audioCodecButtonGroup.buttonClicked.connect(self.onAudioCodecButtonClicked)

        # Основные настройки: сетка для выравнивания 3 строк (CRF–Bitrate–FPS, аудио–частота–keyint, profile–pixel–tune)
        parent_4 = self.ui.verticalLayoutWidget_4
        grid = QGridLayout()
        grid.setSpacing(8)
        # Ширины колонок: подписи и поля в одну колонку
        label_w = 100
        field_w = 72

        # Строка 0: CRF — Bitrate — FPS
        l0 = QLabel("CRF:")
        l0.setMinimumWidth(label_w)
        grid.addWidget(l0, 0, 0)
        self._crfSpin = QSpinBox(parent_4)
        self._crfSpin.setRange(0, 51)
        # self._crfSpin.setValue(23)
        self._crfSpin.setSpecialValueText("—")
        self._crfSpin.setMinimumWidth(field_w)
        grid.addWidget(self._crfSpin, 0, 1)
        l1 = QLabel("Bitrate (k):")
        l1.setMinimumWidth(label_w)
        grid.addWidget(l1, 0, 2)
        self._bitrateSpin = QSpinBox(parent_4)
        self._bitrateSpin.setRange(0, 100000)
        self._bitrateSpin.setValue(0)
        self._bitrateSpin.setSpecialValueText("—")
        self._bitrateSpin.setSingleStep(100)
        self._bitrateSpin.setMinimumWidth(field_w)
        grid.addWidget(self._bitrateSpin, 0, 3)
        l2 = QLabel("FPS:")
        l2.setMinimumWidth(label_w)
        grid.addWidget(l2, 0, 4)
        self._fpsSpin = QSpinBox(parent_4)
        self._fpsSpin.setRange(0, 120)
        self._fpsSpin.setValue(0)
        self._fpsSpin.setSpecialValueText("—")
        self._fpsSpin.setMinimumWidth(field_w)
        grid.addWidget(self._fpsSpin, 0, 5)

        # Строка 1: Аудио битрейт — Частота — Keyint
        l3 = QLabel("Аудио битрейт (k):")
        l3.setMinimumWidth(label_w / 2 + 50)
        grid.addWidget(l3, 1, 0)
        self._audioBitrateSpin = QSpinBox(parent_4)
        self._audioBitrateSpin.setRange(0, 2000)
        self._audioBitrateSpin.setValue(0)
        self._audioBitrateSpin.setSpecialValueText("—")
        self._audioBitrateSpin.setMinimumWidth(field_w)
        grid.addWidget(self._audioBitrateSpin, 1, 1)
        l4 = QLabel("Частота (Hz):")
        l4.setMinimumWidth(label_w)
        grid.addWidget(l4, 1, 2)
        self._sampleRateSpin = QSpinBox(parent_4)
        self._sampleRateSpin.setRange(0, 192000)
        self._sampleRateSpin.setValue(0)
        self._sampleRateSpin.setSpecialValueText("—")
        self._sampleRateSpin.setMinimumWidth(field_w)
        grid.addWidget(self._sampleRateSpin, 1, 3)
        l5 = QLabel("Keyint:")
        l5.setMinimumWidth(label_w)
        grid.addWidget(l5, 1, 4)
        self._keyintSpin = QSpinBox(parent_4)
        self._keyintSpin.setRange(0, 10000)
        self._keyintSpin.setValue(0)
        self._keyintSpin.setSpecialValueText("—")
        self._keyintSpin.setMinimumWidth(field_w)
        self._keyintSpin.setToolTip("Интервал ключевых кадров (-g), 0 = не задано")
        grid.addWidget(self._keyintSpin, 1, 5)

        # Строка 2: Profile/Level — Pixel format — Tune
        l6 = QLabel("Profile/Level:")
        l6.setMinimumWidth(label_w)
        grid.addWidget(l6, 2, 0)
        self._profileLevelEdit = QLineEdit(parent_4)
        self._profileLevelEdit.setPlaceholderText("high:4.1…")
        self._profileLevelEdit.setMinimumWidth(100)
        grid.addWidget(self._profileLevelEdit, 2, 1)
        l7 = QLabel("Pixel format:")
        l7.setMinimumWidth(label_w)
        grid.addWidget(l7, 2, 2)
        self._pixelFormatEdit = QLineEdit(parent_4)
        self._pixelFormatEdit.setPlaceholderText("yuv420p")
        self._pixelFormatEdit.setMinimumWidth(80)
        grid.addWidget(self._pixelFormatEdit, 2, 3)
        l8 = QLabel("Tune:")
        l8.setMinimumWidth(label_w)
        grid.addWidget(l8, 2, 4)
        self._tuneEdit = QLineEdit(parent_4)
        self._tuneEdit.setPlaceholderText("film…")
        self._tuneEdit.setMinimumWidth(80)
        grid.addWidget(self._tuneEdit, 2, 5)

        # Строка 3: колонка 0 — чекбоксы друг под другом; на том же уровне — Preset и Threads
        col0_widget = QWidget(parent_4)
        col0_layout = QVBoxLayout(col0_widget)
        col0_layout.setContentsMargins(0, 0, 0, 0)
        col0_layout.setSpacing(4)
        self._checkTagHvc1 = QCheckBox(parent_4)
        self._checkTagHvc1.setText("-tag:v hvc1")
        self._checkTagHvc1.setToolTip("Для совместимости HEVC")
        col0_layout.addWidget(self._checkTagHvc1)
        self._checkVfLanczos = QCheckBox(parent_4)
        self._checkVfLanczos.setText(":flags=lanczos")
        self._checkVfLanczos.setToolTip("-vf scale=1280x720:flags=lanczos")
        col0_layout.addWidget(self._checkVfLanczos)
        grid.addWidget(col0_widget, 3, 0, 1, 2)
        l_preset = QLabel("Preset:")
        l_preset.setMinimumWidth(label_w)
        grid.addWidget(l_preset, 3, 2)
        self._presetCombo = QComboBox(parent_4)
        for p in ["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow", "placebo"]:
            self._presetCombo.addItem(p)
        self._presetCombo.setCurrentIndex(5)
        self._presetCombo.setMinimumWidth(100)
        grid.addWidget(self._presetCombo, 3, 3)
        l_threads = QLabel("Threads:")
        l_threads.setMinimumWidth(label_w)
        grid.addWidget(l_threads, 3, 4)
        self._threadsSpin = QSpinBox(parent_4)
        self._threadsSpin.setRange(0, 64)
        self._threadsSpin.setValue(0)
        self._threadsSpin.setSpecialValueText("auto")
        self._threadsSpin.setMinimumWidth(80)
        grid.addWidget(self._threadsSpin, 3, 5)

        self.ui.presetSettingsLayout.addLayout(grid)

        # Выделение значения в спинбоксе при фокусе (чтобы "—" сразу заменялся вводом)
        self._spinSelectAllOnFocus.add(self._bitrateSpin)
        self._bitrateSpin.installEventFilter(self)

        # Предупреждения по конфликтным параметрам
        self._warningLabel = QLabel("")
        self._warningLabel.setStyleSheet("color: #ff6666;")
        self._warningLabel.setWordWrap(True)
        self._warningLabel.hide()
        self.ui.presetSettingsLayout.addWidget(self._warningLabel)

        # Информация о extra_args пресета
        self._extraLabel = QLabel("")
        self._extraLabel.setStyleSheet("color: #8fb5ff;")
        self._extraLabel.setWordWrap(True)
        self._extraLabel.hide()
        self.ui.presetSettingsLayout.addWidget(self._extraLabel)

        # Более тёмная область выпадающего списка для QComboBox
        combo_style = (
            "QComboBox::drop-down {"
            "  background-color: #2f2f2f;"
            "  border-left: 1px solid #505050;"
            "  width: 18px;"
            "}"
        )
        self._presetCombo.setStyleSheet(combo_style)

        for w in (self._crfSpin, self._bitrateSpin, self._fpsSpin, self._audioBitrateSpin, self._sampleRateSpin,
                  self._keyintSpin, self._presetCombo, self._profileLevelEdit, self._pixelFormatEdit, self._tuneEdit, self._threadsSpin,
                  self._checkTagHvc1, self._checkVfLanczos):
            if hasattr(w, 'valueChanged'):
                w.valueChanged.connect(self.updateCommandFromPresetEditor)
            elif hasattr(w, 'currentIndexChanged'):
                w.currentIndexChanged.connect(self.updateCommandFromPresetEditor)
            elif hasattr(w, 'textChanged'):
                w.textChanged.connect(self.updateCommandFromPresetEditor)
            elif hasattr(w, 'stateChanged'):
                w.stateChanged.connect(self.updateCommandFromPresetEditor)

        # Подключаем обновление команды при изменении параметров в редакторе
        if hasattr(self, 'codecButtonGroup'):
            self.codecButtonGroup.buttonClicked.connect(self.updateCommandFromPresetEditor)
        if hasattr(self, 'containerButtonGroup'):
            self.containerButtonGroup.buttonClicked.connect(self.updateCommandFromPresetEditor)
        if hasattr(self, 'resolutionButtonGroup'):
            self.resolutionButtonGroup.buttonClicked.connect(self.updateCommandFromPresetEditor)

        # Подключаем сигнал выбора строки в таблице пресетов
        if hasattr(self.ui, 'presetsTableWidget'):
            self.ui.presetsTableWidget.itemSelectionChanged.connect(self.onPresetTableSelectionChanged)

        # Начальные состояния кнопок: current
        if hasattr(self.ui, 'codecCurrentButton'):
            self.ui.codecCurrentButton.setChecked(True)
        if hasattr(self.ui, 'containerCurrentButton'):
            self.ui.containerCurrentButton.setChecked(True)
        if hasattr(self.ui, 'resolutionCurrentButton'):
            self.ui.resolutionCurrentButton.setChecked(True)

        # Заполняем таблицу пресетов
        self.refreshPresetsTable()
    
    def setupDragAndDrop(self):
        """Настраивает drag-and-drop для таблицы"""
        if not hasattr(self.ui, 'queueTableWidget'):
            return
        
        table = self.ui.queueTableWidget
        
        # Переопределяем методы через установку обработчиков
        # В PySide6 можно использовать eventFilter или переопределить методы
        # Для простоты используем прямой подход через переопределение класса
        
        # Создаём обёртку для обработки drag-and-drop
        class QueueTableWidget(table.__class__):
            def __init__(self, parent):
                super().__init__(parent)
                self.main_window = parent
            
            def dragEnterEvent(self, event: QDragEnterEvent):
                if event.mimeData().hasUrls():
                    event.acceptProposedAction()
                else:
                    event.ignore()
            
            def dragMoveEvent(self, event):
                if event.mimeData().hasUrls():
                    event.acceptProposedAction()
                else:
                    event.ignore()
            
            def dropEvent(self, event: QDropEvent):
                if event.mimeData().hasUrls():
                    event.acceptProposedAction()
                    urls = event.mimeData().urls()
                    for url in urls:
                        file_path = url.toLocalFile()
                        if os.path.isfile(file_path):
                            # Проверяем расширение файла
                            ext = os.path.splitext(file_path)[1].lower()
                            if ext in ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv']:
                                self.main_window.addFileToQueue(file_path)
                else:
                    event.ignore()
        
        # Заменяем класс таблицы (это сложно, поэтому используем другой подход)
        # Вместо этого добавим обработчики событий напрямую
        
        # Создаём класс-обёртку для обработки drag-and-drop
        # В PySide6 можно переопределить методы через установку атрибутов
        class DragDropTable:
            def __init__(self, main_window, table):
                self.main_window = main_window
                self.table = table
            
            def dragEnterEvent(self, event):
                if event.mimeData().hasUrls():
                    event.acceptProposedAction()
                else:
                    event.ignore()
            
            def dragMoveEvent(self, event):
                if event.mimeData().hasUrls():
                    event.acceptProposedAction()
                else:
                    event.ignore()
            
            def dropEvent(self, event):
                if event.mimeData().hasUrls():
                    event.acceptProposedAction()
                    urls = event.mimeData().urls()
                    for url in urls:
                        file_path = url.toLocalFile()
                        if os.path.isfile(file_path):
                            ext = os.path.splitext(file_path)[1].lower()
                            if ext in ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv']:
                                self.main_window.addFileToQueue(file_path)
                else:
                    event.ignore()
        
        # Устанавливаем обработчики через monkey patching
        wrapper = DragDropTable(self, table)
        table.dragEnterEvent = wrapper.dragEnterEvent
        table.dragMoveEvent = wrapper.dragMoveEvent
        table.dropEvent = wrapper.dropEvent
    

    def initVideoPreview(self):
        """Инициализирует медиаплеер для предпросмотра видео"""
        try:
            # Создаём медиаплеер
            self.mediaPlayer = QMediaPlayer(self)
            self.audioOutput = QAudioOutput(self)
            self.mediaPlayer.setAudioOutput(self.audioOutput)
            
            # Создаём виджет для видео (если он существует в UI)
            if hasattr(self.ui, 'videoPreviewWidget'):
                # Размер 16:9 (384x216), чтобы 1920x1080 помещалось без чёрных полос
                self.ui.videoPreviewWidget.setFixedSize(384, 216)
                # Отступ слева 8 px — видео по центру относительно кнопок ниже
                if hasattr(self.ui, 'verticalLayout'):
                    self.ui.verticalLayout.setContentsMargins(16, 0, 0, 0)
                self.videoWidget = QVideoWidget(self.ui.videoPreviewWidget)
                self.videoWidget.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
                layout = QVBoxLayout(self.ui.videoPreviewWidget)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.addWidget(self.videoWidget)
                self.mediaPlayer.setVideoOutput(self.videoWidget)
            
            # Подключаем сигналы медиаплеера
            self.mediaPlayer.durationChanged.connect(self.onVideoDurationChanged)
            self.mediaPlayer.positionChanged.connect(self.onVideoPositionChanged)
            self.mediaPlayer.playbackStateChanged.connect(self.onVideoPlaybackStateChanged)
            
            # Изначально звук включен
            self.audioOutput.setVolume(1.0)
            self.isMuted = False
            # Полоска меток обрезки под слайдером
            if hasattr(self.ui, 'verticalLayout') and hasattr(self.ui, 'videoTimelineSlider'):
                self.trimSegmentBar = TrimSegmentBar(self.ui.videoTimelineSlider.parent())
                self.ui.verticalLayout.insertWidget(2, self.trimSegmentBar)  # между слайдером и кнопками
                self._updateTrimSegmentBar()
            # Клик по таймлайну — перемотка в указанное место (не только перетаскивание)
            if hasattr(self.ui, 'videoTimelineSlider'):
                self.ui.videoTimelineSlider.installEventFilter(self)
        except Exception as e:
            print(f"Ошибка инициализации медиаплеера: {e}")
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
    
    def addFilesToQueue(self):
        """Добавляет файлы в очередь через диалог выбора"""
        files, _ = QFileDialog.getOpenFileNames(
            self, 
            "Выберите видео файлы", 
            "", 
            "Видео (*.mp4 *.mkv *.avi *.mov *.flv *.wmv)"
        )
        for file_path in files:
            self.addFileToQueue(file_path)
    
    def addFileToQueue(self, file_path):
        """Добавляет один файл в очередь"""
        if not file_path or not os.path.exists(file_path):
            return
        
        # Проверяем, не добавлен ли уже этот файл
        for item in self.queue:
            if item.file_path == file_path:
                QMessageBox.information(self, "Информация", f"Файл уже в очереди:\n{file_path}")
                return
        
        # Создаём новый элемент очереди
        queue_item = QueueItem(file_path)
        self.queue.append(queue_item)
        
        # Сразу генерируем выходной файл для нового элемента
        self._generateOutputFileForItem(queue_item)
        
        # Обновляем таблицу
        self.updateQueueTable()
        self.updateTotalQueueProgress()
        
        # Выделяем добавленный файл
        self.selectQueueItem(len(self.queue) - 1)
    
    def removeSelectedFromQueue(self):
        """Удаляет выделенный файл из очереди"""
        if self.selectedQueueIndex < 0 or self.selectedQueueIndex >= len(self.queue):
            return
        
        # Не удаляем файл, который сейчас обрабатывается
        if self.selectedQueueIndex == self.currentQueueIndex:
            QMessageBox.warning(self, "Предупреждение", "Нельзя удалить файл, который сейчас обрабатывается")
            return
        
        removed_index = self.selectedQueueIndex

        # Удаляем из очереди
        del self.queue[self.selectedQueueIndex]
        
        # Обновляем индексы
        if self.currentQueueIndex > self.selectedQueueIndex:
            self.currentQueueIndex -= 1
        
        # Обновляем таблицу и выделение, аккуратно блокируя сигналы,
        # чтобы избежать рекурсивных вызовов itemSelectionChanged.
        table = self.ui.queueTableWidget if hasattr(self.ui, 'queueTableWidget') else None
        if table:
            table.blockSignals(True)
            self.updateQueueTable()
            if self.queue:
                # Пытаемся выделить элемент, который шёл следом за удалённым
                new_index = min(removed_index, len(self.queue) - 1)
                # Устанавливаем индекс до вызова selectRow, чтобы избежать лишних вызовов
                self.selectedQueueIndex = new_index
                table.clearSelection()
                table.selectRow(new_index)
                # Восстанавливаем сигналы перед вызовом selectQueueItem, чтобы он мог обновить UI
                table.blockSignals(False)
                # Вызываем selectQueueItem напрямую, чтобы обновить команду и редактор пресетов
                # без повторного вызова через сигнал
                self.selectQueueItem(new_index)
            else:
                # Очередь пуста — сбрасываем состояние,
                # но больше не трогаем окно настроек пресетов.
                self.selectedQueueIndex = -1
                table.clearSelection()
                self.inputFile = ""
                if hasattr(self.ui, 'commandDisplay'):
                    self.ui.commandDisplay.clear()
                table.blockSignals(False)
        else:
            # На всякий случай, если таблицы нет
            self.updateQueueTable()
    
    def updateQueueTable(self):
        """Обновляет отображение таблицы очереди"""
        if not hasattr(self.ui, 'queueTableWidget'):
            return

        table = self.ui.queueTableWidget

        # Блокируем сигналы чтобы избежать рекурсии при обновлении таблицы
        table.blockSignals(True)

        table.setRowCount(len(self.queue))

        for row, item in enumerate(self.queue):
            # Столбец 0: Входной файл
            # Показываем только название файла с расширением.
            # Длинные имена обрезаем до 25 символов и добавляем '...'.
            full_input_name = os.path.basename(item.file_path) if item.file_path else ""
            input_name = self._truncateNameForDisplay(full_input_name, 25)
            file_item = QTableWidgetItem(input_name)
            file_item.setFlags(file_item.flags() & ~Qt.ItemIsEditable)
            file_item.setToolTip(item.file_path)  # Полный путь в подсказке
            table.setItem(row, 0, file_item)

            # Столбец 1: Выходной файл
            output_file_path = item.output_file if item.output_file else ""
            # Показываем только имя файла с расширением, обрезая до 25 символов.
            if output_file_path:
                full_output_name = os.path.basename(output_file_path)
                display_output = self._truncateNameForDisplay(full_output_name, 25)
            else:
                display_output = ""
            output_item = QTableWidgetItem(display_output)
            output_item.setToolTip(output_file_path)  # Полный путь в подсказке
            # Делаем НЕредактируемым - изменения через двойной клик
            output_item.setFlags(output_item.flags() & ~Qt.ItemIsEditable)
            table.setItem(row, 1, output_item)

            # Столбец 2: Пресет
            preset_text = item.preset_name if item.preset_name else "default"
            if isinstance(preset_text, str) and preset_text.startswith("cmd:"):
                preset_text = f"cmd + {preset_text[4:]}"
            preset_item = QTableWidgetItem(preset_text)
            preset_item.setFlags(preset_item.flags() & ~Qt.ItemIsEditable)
            table.setItem(row, 2, preset_item)

            # Столбец 3: Статус
            status_item = QTableWidgetItem(item.getStatusText())
            status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
            table.setItem(row, 3, status_item)

            # Столбец 4: Прогресс
            progress_text = f"{item.progress}%"
            progress_item = QTableWidgetItem(progress_text)
            progress_item.setFlags(progress_item.flags() & ~Qt.ItemIsEditable)
            table.setItem(row, 4, progress_item)

            # Столбец 5: Кнопка "Открыть" (только для завершенных файлов)
            if item.status == QueueItem.STATUS_SUCCESS and item.output_file:
                open_btn = QPushButton("Открыть")
                open_btn.setMaximumHeight(22)
                open_btn.setStyleSheet("padding: 2px 4px; font-size: 10px; min-height: 0;")
                open_btn.clicked.connect(lambda _, path=item.output_file: self.openFileLocation(path))
                table.setCellWidget(row, 5, open_btn)
            else:
                # Для незавершенных файлов - пустая ячейка
                empty_item = QTableWidgetItem("")
                empty_item.setFlags(empty_item.flags() & ~Qt.ItemIsEditable)
                table.setItem(row, 5, empty_item)

        # Восстанавливаем сигналы
        table.blockSignals(False)
        # Пустая таблица — без нумерации и без пустого места; при строках — нумерация за счёт колонок 0 и 1
        self._applyQueueTableColumnWidths()

    def selectQueueItem(self, index):
        """Выделяет элемент очереди по индексу"""
        if not hasattr(self.ui, 'queueTableWidget') or index < 0 or index >= len(self.queue):
            return
        
        # Если уже выделен этот элемент, не делаем ничего
        if self.selectedQueueIndex == index:
            return
        
        table = self.ui.queueTableWidget
        # Блокируем сигналы, чтобы избежать рекурсивных вызовов
        table.blockSignals(True)
        table.selectRow(index)
        table.blockSignals(False)
        self.selectedQueueIndex = index
        
        # Загружаем файл в предпросмотр и обновляем команду
        item = self.queue[index]
        self.inputFile = item.file_path
        
        # Если выходной файл не задан, генерируем его
        if not item.output_file:
            self._generateOutputFileForItem(item)
        
        # Сбрасываем длительность до загрузки нового видео, чтобы полоска обрезки не показывала масштаб прошлого
        self.videoDuration = 0
        # Загружаем видео
        self.loadVideoForPreview()

        # Восстанавливаем команду для этого элемента:
        # если пользователь уже редактировал её вручную — показываем именно её,
        # иначе генерируем команду из текущих параметров.
        if getattr(item, "command_manually_edited", False) and getattr(item, "command", ""):
            if isinstance(item.preset_name, str) and item.preset_name.startswith("cmd:"):
                self._applyPathsToSavedCommand(item)
            self.commandManuallyEdited = True
            self.lastGeneratedCommand = getattr(item, "last_generated_command", "")
            self.ui.commandDisplay.setPlainText(item.command)
        else:
            self.commandManuallyEdited = False
            self.updateCommandFromGUI()

        # Обновляем редактор пресетов под текущий файл
        self.syncPresetEditorWithQueueItem(item)

        # Полоска обрезки привязана к каждой позиции очереди — показываем данные этого файла
        self._updateTrimSegmentBar()
    
    def onQueueItemSelected(self):
        """Обработчик выделения элемента в таблице"""
        table = self.ui.queueTableWidget
        selected_rows = table.selectionModel().selectedRows()
        indices = sorted([r.row() for r in selected_rows])

        if not indices:
            # Если ничего не выделено, просто сбрасываем индекс,
            # но не скрываем окно настроек пресетов и не меняем размер окна.
            self.selectedQueueIndex = -1
            # Очищаем отображение команды и блокируем редактирование
            if hasattr(self.ui, 'commandDisplay'):
                self.ui.commandDisplay.clear()
                self.ui.commandDisplay.setReadOnly(True)
            # Останавливаем предпросмотр
            if hasattr(self, 'mediaPlayer') and self.mediaPlayer:
                self.mediaPlayer.stop()
            # Полоска обрезки привязана к позиции очереди — для «нет выбора» показываем пустую
            self._updateTrimSegmentBar()
            return

        if len(indices) == 1:
            row = indices[0]
            if 0 <= row < len(self.queue) and row != self.selectedQueueIndex:
                # Один файл — обычное поведение
                if hasattr(self.ui, 'commandDisplay'):
                    self.ui.commandDisplay.setReadOnly(False)
                self.selectQueueItem(row)
        else:
            # Несколько файлов выделено:
            #  - не показываем команду FFmpeg
            #  - блокируем предпросмотр видео
            self.selectedQueueIndex = -1
            if hasattr(self.ui, 'commandDisplay'):
                self.ui.commandDisplay.clear()
                self.ui.commandDisplay.setReadOnly(True)
            if hasattr(self, 'mediaPlayer') and self.mediaPlayer:
                self.mediaPlayer.stop()
            self._updateTrimSegmentBar()
    
    def onQueueCellDoubleClicked(self, row, column):
        """Обработчик двойного клика по ячейке таблицы"""
        if column == 1:  # Клик по столбцу "Выходной файл"
            self.selectOutputFileForQueueItem(row)
        # Двойной клик по колонке "Пресет" больше не обрабатывается

    def selectOutputFileForQueueItem(self, row):
        """Открывает диалог выбора выходного файла для элемента очереди"""
        if row < 0 or row >= len(self.queue):
            return

        item = self.queue[row]

        # Определяем начальную директорию и имя файла
        if item.output_file:
            initial_dir = os.path.dirname(item.output_file)
            initial_name = os.path.splitext(os.path.basename(item.output_file))[0]  # Убираем расширение
        else:
            # Если выходной файл не задан, используем директорию входного файла
            initial_dir = os.path.dirname(item.file_path)
            input_base = os.path.splitext(os.path.basename(item.file_path))[0]
            initial_name = input_base + "_converted"

        # Определяем расширение на основе контейнера для фильтра
        container = item.container or "current"
        if container in ("default", "current", "", None):
            container_ext = os.path.splitext(item.file_path)[1].lstrip(".")
        else:
            container_ext = container

        # Создаем фильтр с нужным расширением
        if container_ext:
            file_filter = f"{container_ext.upper()} файлы (*.{container_ext});;Все файлы (*.*)"
        else:
            file_filter = "Все файлы (*.*)"

        # Открываем диалог сохранения файла
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Выберите выходной файл",
            os.path.join(initial_dir, initial_name),
            file_filter
        )

        if file_path:
            # Сохраняем выбранный путь (расширение будет добавлено при генерации команды)
            item.output_file = file_path
            # Обновляем таблицу
            self.updateQueueTable()

            # Если это выделенный файл, обновляем команду
            if row == self.selectedQueueIndex:
                if isinstance(item.preset_name, str) and item.preset_name.startswith("cmd:"):
                    self._applyPathsToSavedCommand(item, update_display=True)
                else:
                    self.updateCommandFromGUI()

    def updateCommandFromGUI(self):
        """Обновляет команду только если она не была отредактирована вручную"""
        item = self.getSelectedQueueItem()
        if not item:
            if hasattr(self.ui, 'commandDisplay'):
                self.ui.commandDisplay.setPlainText("ffmpeg")
            return
        
        # Автоматическая генерация команды только если пользователь не правил её вручную
        if not self.commandManuallyEdited:
            new_cmd = self.generateFFmpegCommand()
            self.lastGeneratedCommand = new_cmd
            if hasattr(self.ui, 'commandDisplay'):
                # Блокируем сигналы, чтобы программное обновление текста
                # не считалось ручным редактированием и не портило preset_name.
                cmd_widget = self.ui.commandDisplay
                cmd_widget.blockSignals(True)
                cmd_widget.setPlainText(new_cmd)
                cmd_widget.blockSignals(False)
            # Сохраняем автосгенерированную команду в QueueItem
            item.last_generated_command = new_cmd
            item.command = new_cmd
            item.command_manually_edited = False
        else:
            # Если команда уже была отредактирована вручную, просто обновим
            # сохранённое значение в QueueItem (на случай, если пользователь поправил что‑то ещё)
            item.command = self.ui.commandDisplay.toPlainText()
        
        # Таблица обновляется вызывающим кодом
    
    def onCommandManuallyEdited(self):
        """Отслеживает ручное редактирование команды"""
        item = self.getSelectedQueueItem()
        if not item:
            return

        current_cmd = self.ui.commandDisplay.toPlainText()
        last_generated = getattr(item, "last_generated_command", self.lastGeneratedCommand)

        if current_cmd != last_generated:
            # Пользователь отошёл от автоматически сгенерированной команды
            self.commandManuallyEdited = True
            item.command_manually_edited = True
            item.command = current_cmd
            # При ручном редактировании считаем, что для файла используется кастомный пресет
            if not (isinstance(item.preset_name, str) and item.preset_name.startswith("cmd:")):
                item.preset_name = "custom"
        else:
            # Команда снова совпала с автогенерацией — считаем, что она не редактировалась вручную
            self.commandManuallyEdited = False
            item.command_manually_edited = False

    def _quotePath(self, path):
        """Всегда оборачивает путь в кавычки для безопасности."""
        if not path:
            return '""'
        # Если путь уже в кавычках — возвращаем как есть
        if path.startswith('"') and path.endswith('"'):
            return path
        return f'"{path}"'

    def _truncatePathFromStart(self, path, max_length=25):
        """Показывает последние max_length символов пути"""
        if len(path) <= max_length:
            return path
        return "..." + path[-max_length:]

    def _truncateNameForDisplay(self, name, max_length=25):
        """Возвращает первые max_length символов имени файла + '...' если оно длиннее."""
        if not name:
            return ""
        if len(name) <= max_length:
            return name
        return name[:max_length] + "..."

    # ===== Вспомогательные методы для редактора пресетов =====

    def refreshPresetsTable(self):
        """Перечитывает presets.xml и обновляет таблицу пресетов."""
        if not hasattr(self.ui, 'presetsTableWidget'):
            return

        table = self.ui.presetsTableWidget
        presets = self.presetManager.loadAllPresets()
        table.setRowCount(len(presets))

        for row, p in enumerate(presets):
            name_text = p["name"]
            extra_hint = p.get("extra_args", "") or ""
            if extra_hint.strip():
                name_text = f"{p['name']} +extra"
            name_item = QTableWidgetItem(name_text)
            desc_item = QTableWidgetItem(p.get("description", ""))
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            desc_item.setFlags(desc_item.flags() & ~Qt.ItemIsEditable)
            # При наведении показываем полное название и полное описание
            name_item.setToolTip(p["name"])
            name_item.setData(Qt.UserRole, p["name"])
            desc_tooltip = p.get("description", "")
            if extra_hint.strip():
                desc_tooltip = (desc_tooltip + "\n" if desc_tooltip else "") + f"Extra: {extra_hint}"
            desc_item.setToolTip(desc_tooltip)
            table.setItem(row, 0, name_item)
            table.setItem(row, 1, desc_item)

            # Кнопка "Удалить пресет" — компактная
            delete_btn = QPushButton("Удалить")
            delete_btn.setMaximumHeight(20)
            delete_btn.setStyleSheet("padding: 1px 4px; font-size: 10px; min-height: 0;")
            delete_btn.clicked.connect(lambda _, n=p["name"]: self.onDeletePresetClicked(n))
            table.setCellWidget(row, 2, delete_btn)

            # Кнопка "Применить" — компактная
            apply_btn = QPushButton("Применить")
            apply_btn.setMaximumHeight(20)
            apply_btn.setStyleSheet("padding: 1px 4px; font-size: 10px; min-height: 0;")
            apply_btn.clicked.connect(lambda _, n=p["name"]: self.onApplyPresetClicked(n))
            table.setCellWidget(row, 3, apply_btn)

    def _getSelectedPresetName(self):
        if not hasattr(self.ui, 'presetsTableWidget'):
            return None, -1
        table = self.ui.presetsTableWidget
        row = table.currentRow()
        if row < 0:
            return None, -1
        name_item = table.item(row, 0)
        if not name_item:
            return None, -1
        return name_item.data(Qt.UserRole) or name_item.text(), row

    def movePresetUp(self):
        name, row = self._getSelectedPresetName()
        if not name:
            return
        if self.presetManager.movePreset(name, "up"):
            self.refreshPresetsTable()
            if hasattr(self.ui, 'presetsTableWidget'):
                self.ui.presetsTableWidget.setCurrentCell(max(row - 1, 0), 0)
                self.onPresetTableSelectionChanged()

    def movePresetDown(self):
        name, row = self._getSelectedPresetName()
        if not name:
            return
        if self.presetManager.movePreset(name, "down"):
            self.refreshPresetsTable()
            if hasattr(self.ui, 'presetsTableWidget'):
                table = self.ui.presetsTableWidget
                new_row = min(row + 1, table.rowCount() - 1)
                table.setCurrentCell(new_row, 0)
                self.onPresetTableSelectionChanged()

    def onDeletePresetClicked(self, name):
        if not name:
            return
        ret = QMessageBox.question(
            self,
            "Удаление пресета",
            f"Удалить пресет \"{name}\"?",
            QMessageBox.Yes | QMessageBox.No
        )
        if ret != QMessageBox.Yes:
            return
        self.presetManager.removePreset(name)
        self.refreshPresetsTable()

    def onQueueItemChanged(self, item):
        """Обработчик изменения ячейки в таблице очереди."""
        # Пока не используется, так как редактирование ячеек отключено
        pass

    def onPresetTableSelectionChanged(self):
        """Загружает выбранный в таблице пресет в редактор пресетов."""
        if not hasattr(self.ui, 'presetsTableWidget'):
            return
        table = self.ui.presetsTableWidget
        row = table.currentRow()
        if row < 0:
            return
        name_item = table.item(row, 0)
        if not name_item:
            return
        preset_name = name_item.data(Qt.UserRole) or name_item.text()
        preset = self.presetManager.loadPreset(preset_name)
        if preset:
            self.currentPresetName = preset_name
            self.syncPresetEditorWithPresetData(preset)

    def onApplyPresetClicked(self, name):
        """Применяет выбранный пресет к выделенным файлам в очереди и обновляет редактор."""
        table = self.ui.queueTableWidget if hasattr(self.ui, 'queueTableWidget') else None
        if not table:
            return
        selected_rows = table.selectionModel().selectedRows()
        indices = sorted([r.row() for r in selected_rows])
        if not indices:
            QMessageBox.information(self, "Очередь", "Сначала выберите файл(ы) в очереди.")
            return

        preset = self.presetManager.loadPreset(name)
        if not preset:
            QMessageBox.warning(self, "Пресеты", "Не удалось загрузить пресет.")
            return

        # Применяем пресет ко всем выделенным элементам
        for idx in indices:
            if 0 <= idx < len(self.queue):
                item = self.queue[idx]
                item.preset_name = name
                item.setPreset(preset)

                # При выборе нового пресета сбрасываем флаг ручного редактирования команды
                item.command_manually_edited = False

                # Обновляем выходной файл при изменении контейнера
                container = preset.get('container', 'current')
                if container not in ("default", "current", "", None):
                    if item.output_file:
                        # Меняем расширение в пути
                        base_path = os.path.splitext(item.output_file)[0]
                        item.output_file = base_path + "." + container
                    else:
                        # Если выходной файл не задан, генерируем его
                        self._generateOutputFileForItem(item)
                elif not item.output_file:
                    # Если контейнер "current" или "default", но выходной файл не задан, генерируем его
                    self._generateOutputFileForItem(item)

        # Запоминаем текущий выбранный пресет в редакторе
        self.currentPresetName = name
        # Сбрасываем глобальный флаг ручного редактирования для текущего файла
        self.commandManuallyEdited = False

        # Синхронизируем кнопки редактора пресетов (отключаем сигналы чтобы не вызвать лишние обновления)
        if hasattr(self, 'codecButtonGroup'):
            self.codecButtonGroup.blockSignals(True)
        if hasattr(self, 'containerButtonGroup'):
            self.containerButtonGroup.blockSignals(True)
        if hasattr(self, 'resolutionButtonGroup'):
            self.resolutionButtonGroup.blockSignals(True)

        self.syncPresetEditorWithPresetData(preset)

        # Восстанавливаем сигналы
        if hasattr(self, 'codecButtonGroup'):
            self.codecButtonGroup.blockSignals(False)
        if hasattr(self, 'containerButtonGroup'):
            self.containerButtonGroup.blockSignals(False)
        if hasattr(self, 'resolutionButtonGroup'):
            self.resolutionButtonGroup.blockSignals(False)

        # Обновляем таблицу (команда для файлов будет регенерирована при их выборе
        # и при запуске очереди, так как параметры уже изменены в QueueItem)
        self.updateQueueTable()

        # Если выбран один файл — сразу обновляем команду в окне
        if len(indices) == 1:
            self.selectedQueueIndex = indices[0]
            if hasattr(self.ui, 'commandDisplay'):
                self.ui.commandDisplay.setReadOnly(False)
            self.updateCommandFromGUI()

    def _getCodecFromButtons(self):
        """Возвращает строковое значение видеокодека на основе нажатой кнопки."""
        if hasattr(self.ui, 'codecCurrentButton') and self.ui.codecCurrentButton.isChecked():
            return "current"
        if hasattr(self.ui, 'codecLibx264Button') and self.ui.codecLibx264Button.isChecked():
            return "libx264"
        if hasattr(self.ui, 'codecLibx265Button') and self.ui.codecLibx265Button.isChecked():
            return "libx265"
        if hasattr(self, '_codecProresButton') and self._codecProresButton.isChecked():
            return "prores"
        if hasattr(self.ui, 'codecCustomButton') and self.ui.codecCustomButton.isChecked():
            return self.currentCodecCustom or "current"
        return "current"

    def _getContainerFromButtons(self):
        if hasattr(self.ui, 'containerCurrentButton') and self.ui.containerCurrentButton.isChecked():
            return "current"
        if hasattr(self.ui, 'containerMp4Button') and self.ui.containerMp4Button.isChecked():
            return "mp4"
        if hasattr(self.ui, 'containerMkvButton') and self.ui.containerMkvButton.isChecked():
            return "mkv"
        if hasattr(self, '_containerMovButton') and self._containerMovButton.isChecked():
            return "mov"
        if hasattr(self, '_containerAviButton') and self._containerAviButton.isChecked():
            return "avi"
        if hasattr(self, '_containerMxfButton') and self._containerMxfButton.isChecked():
            return "mxf"
        if hasattr(self.ui, 'containerCustomButton') and self.ui.containerCustomButton.isChecked():
            return self.currentContainerCustom or "current"
        return "current"

    def _getResolutionFromButtons(self):
        if hasattr(self.ui, 'resolutionCurrentButton') and self.ui.resolutionCurrentButton.isChecked():
            return "current"
        if hasattr(self.ui, 'resolution480pButton') and self.ui.resolution480pButton.isChecked():
            return "480p"
        if hasattr(self.ui, 'resolution720pButton') and self.ui.resolution720pButton.isChecked():
            return "720p"
        if hasattr(self.ui, 'resolution1080pButton') and self.ui.resolution1080pButton.isChecked():
            return "1080p"
        if hasattr(self, '_resolution2kButton') and self._resolution2kButton.isChecked():
            return "2k"
        if hasattr(self, '_resolution4kButton') and self._resolution4kButton.isChecked():
            return "4k"
        if hasattr(self.ui, 'resolutionCustomButton') and self.ui.resolutionCustomButton.isChecked():
            return self.currentResolutionCustom or "current"
        return "current"

    def _getAudioCodecFromButtons(self):
        """Возвращает выбранный аудио-кодек."""
        if hasattr(self, '_audioCodecAacButton') and self._audioCodecAacButton.isChecked():
            return "aac"
        if hasattr(self, '_audioCodecMp3Button') and self._audioCodecMp3Button.isChecked():
            return "mp3"
        if hasattr(self, '_audioCodecPcm16Button') and self._audioCodecPcm16Button.isChecked():
            return "pcm_s16le"
        if hasattr(self, '_audioCodecPcm24Button') and self._audioCodecPcm24Button.isChecked():
            return "pcm_s24le"
        if hasattr(self, '_audioCodecCurrentButton') and self._audioCodecCurrentButton.isChecked():
            return "current"
        if hasattr(self, '_audioCodecCustomButton') and self._audioCodecCustomButton.isChecked():
            return self.currentAudioCodecCustom or "aac"
        return "current"

    def onAudioCodecButtonClicked(self, button):
        """Обработчик выбора аудио-кодека. Custom — выпадающее меню."""
        if hasattr(self, '_audioCodecCustomButton') and button is self._audioCodecCustomButton:
            self._showCustomAudioCodecMenu()
            return
        self.updateCommandFromPresetEditor()

    def syncPresetEditorWithPresetData(self, preset):
        """Устанавливает состоние кнопок редактора по данным пресета."""
        self._suppressPresetEditorUpdates = True
        codec = preset.get("codec", "current")
        container = preset.get("container", "current")
        resolution = preset.get("resolution", "current")

        # Кодек
        if codec in ("current", "default"):
            if hasattr(self.ui, 'codecCurrentButton'):
                self.ui.codecCurrentButton.setChecked(True)
        elif codec == "libx264":
            if hasattr(self.ui, 'codecLibx264Button'):
                self.ui.codecLibx264Button.setChecked(True)
        elif codec == "libx265":
            if hasattr(self.ui, 'codecLibx265Button'):
                self.ui.codecLibx265Button.setChecked(True)
        elif codec == "prores" and hasattr(self, '_codecProresButton'):
            self._codecProresButton.setChecked(True)
        elif codec == "copy":
            # copy — скрытая опция, оставляем как custom
            self.currentCodecCustom = "copy"
            if hasattr(self.ui, 'codecCustomButton'):
                self.ui.codecCustomButton.setChecked(True)
        else:
            # Кастомный кодек — добавляем в список сохранённых, если ещё нет
            self.currentCodecCustom = codec
            if codec and codec not in getattr(self, "customCodecs", []):
                self.customCodecs.append(codec)
                self._saveCustomOptions()
            if hasattr(self.ui, 'codecCustomButton'):
                self.ui.codecCustomButton.setChecked(True)

        # Контейнер
        if container in ("current", "default", ""):
            if hasattr(self.ui, 'containerCurrentButton'):
                self.ui.containerCurrentButton.setChecked(True)
        elif container == "mp4":
            if hasattr(self.ui, 'containerMp4Button'):
                self.ui.containerMp4Button.setChecked(True)
        elif container == "mkv":
            if hasattr(self.ui, 'containerMkvButton'):
                self.ui.containerMkvButton.setChecked(True)
        elif container == "mov" and hasattr(self, '_containerMovButton'):
            self._containerMovButton.setChecked(True)
        elif container == "avi" and hasattr(self, '_containerAviButton'):
            self._containerAviButton.setChecked(True)
        elif container == "mxf" and hasattr(self, '_containerMxfButton'):
            self._containerMxfButton.setChecked(True)
        else:
            self.currentContainerCustom = container
            if container and container not in getattr(self, "customContainers", []):
                self.customContainers.append(container)
                self._saveCustomOptions()
            if hasattr(self.ui, 'containerCustomButton'):
                self.ui.containerCustomButton.setChecked(True)

        # Разрешение
        if resolution in ("current", "default", ""):
            if hasattr(self.ui, 'resolutionCurrentButton'):
                self.ui.resolutionCurrentButton.setChecked(True)
        elif resolution == "480p":
            if hasattr(self.ui, 'resolution480pButton'):
                self.ui.resolution480pButton.setChecked(True)
        elif resolution == "720p":
            if hasattr(self.ui, 'resolution720pButton'):
                self.ui.resolution720pButton.setChecked(True)
        elif resolution == "1080p":
            if hasattr(self.ui, 'resolution1080pButton'):
                self.ui.resolution1080pButton.setChecked(True)
        elif resolution == "2k" and hasattr(self, '_resolution2kButton'):
            self._resolution2kButton.setChecked(True)
        elif resolution == "4k" and hasattr(self, '_resolution4kButton'):
            self._resolution4kButton.setChecked(True)
        else:
            self.currentResolutionCustom = resolution if (":" in resolution or "x" in resolution) else resolution
            res_norm = (self.currentResolutionCustom or "").replace("x", ":")
            if res_norm and res_norm not in getattr(self, "customResolutions", []):
                self.customResolutions.append(res_norm)
                self._saveCustomOptions()
            if hasattr(self.ui, 'resolutionCustomButton'):
                self.ui.resolutionCustomButton.setChecked(True)

        # Аудио-кодек (по умолчанию current)
        audio = preset.get("audio_codec", "current")
        if audio == "aac" and hasattr(self, '_audioCodecAacButton'):
            self._audioCodecAacButton.setChecked(True)
        elif audio == "mp3" and hasattr(self, '_audioCodecMp3Button'):
            self._audioCodecMp3Button.setChecked(True)
        elif audio == "pcm_s16le" and hasattr(self, '_audioCodecPcm16Button'):
            self._audioCodecPcm16Button.setChecked(True)
        elif audio == "pcm_s24le" and hasattr(self, '_audioCodecPcm24Button'):
            self._audioCodecPcm24Button.setChecked(True)
        elif audio in ("current", "copy") and hasattr(self, '_audioCodecCurrentButton'):
            self._audioCodecCurrentButton.setChecked(True)
        elif hasattr(self, '_audioCodecCustomButton'):
            self.currentAudioCodecCustom = audio if audio not in ("aac", "mp3", "pcm_s16le", "pcm_s24le", "current") else (self.currentAudioCodecCustom or "aac")
            if self.currentAudioCodecCustom and self.currentAudioCodecCustom not in getattr(self, "customAudioCodecs", []):
                self.customAudioCodecs.append(self.currentAudioCodecCustom)
                self._saveCustomOptions()
            self._audioCodecCustomButton.setChecked(True)

        # Основные настройки
        if hasattr(self, '_crfSpin'):
            self._crfSpin.setValue(int(preset.get("crf", 0) or 0))
        if hasattr(self, '_bitrateSpin'):
            self._bitrateSpin.setValue(int(preset.get("bitrate", 0) or 0))
        if hasattr(self, '_fpsSpin'):
            self._fpsSpin.setValue(int(preset.get("fps", 0) or 0))
        if hasattr(self, '_audioBitrateSpin'):
            self._audioBitrateSpin.setValue(int(preset.get("audio_bitrate", 0) or 0))
        if hasattr(self, '_sampleRateSpin'):
            self._sampleRateSpin.setValue(int(preset.get("sample_rate", 0) or 0))
        if hasattr(self, '_keyintSpin'):
            self._keyintSpin.setValue(int(preset.get("keyint", 0) or 0))
        if hasattr(self, '_presetCombo'):
            idx = self._presetCombo.findText(preset.get("preset_speed", "medium") or "medium")
            if idx >= 0:
                self._presetCombo.setCurrentIndex(idx)
        if hasattr(self, '_profileLevelEdit'):
            self._profileLevelEdit.setText(preset.get("profile_level", "") or "")
        if hasattr(self, '_pixelFormatEdit'):
            self._pixelFormatEdit.setText(preset.get("pixel_format", "") or "")
        if hasattr(self, '_tuneEdit'):
            self._tuneEdit.setText(preset.get("tune", "") or "")
        if hasattr(self, '_threadsSpin'):
            self._threadsSpin.setValue(int(preset.get("threads", 0) or 0))
        if hasattr(self, '_checkTagHvc1'):
            v = preset.get("tag_hvc1", False)
            self._checkTagHvc1.setChecked(v is True or str(v).strip() == "1")
        if hasattr(self, '_checkVfLanczos'):
            v = preset.get("vf_lanczos", False)
            self._checkVfLanczos.setChecked(v is True or str(v).strip() == "1")
        self._suppressPresetEditorUpdates = False
        self._updateConflictWarningsFromEditor()

    def syncPresetEditorWithQueueItem(self, item: QueueItem):
        """При выборе файла в очереди подтягиваем в редактор его текущие параметры."""
        preset_data = {
            "codec": item.codec,
            "container": item.container,
            "resolution": item.resolution,
            "audio_codec": getattr(item, "audio_codec", "current"),
            "crf": getattr(item, "crf", 0),
            "bitrate": getattr(item, "bitrate", 0),
            "fps": getattr(item, "fps", 0),
            "audio_bitrate": getattr(item, "audio_bitrate", 0),
            "sample_rate": getattr(item, "sample_rate", 0),
            "preset_speed": getattr(item, "preset_speed", "medium"),
            "profile_level": getattr(item, "profile_level", ""),
            "pixel_format": getattr(item, "pixel_format", ""),
            "tune": getattr(item, "tune", ""),
            "threads": getattr(item, "threads", 0),
            "keyint": getattr(item, "keyint", False),
            "tag_hvc1": getattr(item, "tag_hvc1", False),
            "vf_lanczos": getattr(item, "vf_lanczos", False),
        }
        self.currentPresetName = item.preset_name
        self.syncPresetEditorWithPresetData(preset_data)

    # --- Обработчики кликов по кнопкам редактора пресетов ---

    def onCodecButtonClicked(self, button):
        """Обработчик выбора кодека в редакторе пресетов. Custom — выпадающее меню."""
        if hasattr(self.ui, 'codecCustomButton') and button is self.ui.codecCustomButton:
            self._showCustomCodecMenu()
            return
        self.updateCommandFromPresetEditor()

    def onContainerButtonClicked(self, button):
        """Обработчик выбора контейнера в редакторе пресетов."""
        if hasattr(self.ui, 'containerCustomButton') and button is self.ui.containerCustomButton:
            self._showCustomContainerMenu()
            return
        self.updateCommandFromPresetEditor()

    def onResolutionButtonClicked(self, button):
        """Обработчик выбора разрешения в редакторе пресетов. Custom — выпадающее меню."""
        if hasattr(self.ui, 'resolutionCustomButton') and button is self.ui.resolutionCustomButton:
            self._showCustomResolutionMenu()
            return
        self.updateCommandFromPresetEditor()

    def updateCommandFromPresetEditor(self):
        """Обновляет команду FFmpeg на основе текущих настроек редактора пресетов."""
        if getattr(self, "_suppressPresetEditorUpdates", False):
            return
        table = self.ui.queueTableWidget if hasattr(self.ui, 'queueTableWidget') else None
        if not table:
            return

        selected_rows = table.selectionModel().selectedRows()
        indices = sorted([r.row() for r in selected_rows])
        if not indices:
            # Нет выделенных файлов — нечего обновлять
            return

        # Получаем текущие значения из кнопок и виджетов редактора
        codec = self._getCodecFromButtons()
        container = self._getContainerFromButtons()
        resolution = self._getResolutionFromButtons()
        audio_codec = self._getAudioCodecFromButtons()
        crf = self._crfSpin.value() if hasattr(self, '_crfSpin') else 0
        bitrate = self._bitrateSpin.value() if hasattr(self, '_bitrateSpin') else 0
        fps = self._fpsSpin.value() if hasattr(self, '_fpsSpin') else 0
        audio_bitrate = self._audioBitrateSpin.value() if hasattr(self, '_audioBitrateSpin') else 0
        sample_rate = self._sampleRateSpin.value() if hasattr(self, '_sampleRateSpin') else 0
        preset_speed = self._presetCombo.currentText() if hasattr(self, '_presetCombo') else "medium"
        profile_level = self._profileLevelEdit.text().strip() if hasattr(self, '_profileLevelEdit') else ""
        pixel_format = self._pixelFormatEdit.text().strip() if hasattr(self, '_pixelFormatEdit') else ""
        tune = self._tuneEdit.text().strip() if hasattr(self, '_tuneEdit') else ""
        threads = self._threadsSpin.value() if hasattr(self, '_threadsSpin') else 0
        keyint = self._keyintSpin.value() if hasattr(self, '_keyintSpin') else 0
        tag_hvc1 = self._checkTagHvc1.isChecked() if hasattr(self, '_checkTagHvc1') else False
        vf_lanczos = self._checkVfLanczos.isChecked() if hasattr(self, '_checkVfLanczos') else False

        # Обновляем параметры во всех выделенных QueueItem
        default_like = ("default", "current", "")
        warned_copy = False
        for idx in indices:
            if 0 <= idx < len(self.queue):
                item = self.queue[idx]

                # Обновляем параметры в QueueItem
                item.codec = codec
                item.container = container
                item.resolution = resolution
                item.audio_codec = audio_codec
                item.crf = crf
                item.bitrate = bitrate
                item.fps = fps
                item.audio_bitrate = audio_bitrate
                item.sample_rate = sample_rate
                item.preset_speed = preset_speed
                item.profile_level = profile_level
                item.pixel_format = pixel_format
                item.tune = tune
                item.threads = threads
                item.keyint = int(keyint)
                item.tag_hvc1 = tag_hvc1
                item.vf_lanczos = vf_lanczos

                # Предупреждение: copy игнорирует фильтры и качество
                if not warned_copy:
                    if codec == "copy" and (vf_lanczos or resolution not in default_like or crf or bitrate or fps or preset_speed or profile_level or pixel_format or tune or threads or keyint):
                        if hasattr(self, "updateStatus"):
                            self.updateStatus("Внимание: при copy видео фильтры/CRF/bitrate/FPS игнорируются.")
                        warned_copy = True
                    if audio_codec == "current" and (audio_bitrate or sample_rate):
                        if hasattr(self, "updateStatus"):
                            self.updateStatus("Внимание: при copy аудио битрейт/частота игнорируются.")
                        warned_copy = True

                # Устанавливаем custom resolution если выбрано
                if resolution == "custom":
                    item.custom_resolution = self.currentResolutionCustom
                else:
                    item.custom_resolution = ""

                # Если пользователь изменил контейнер, обновляем расширение в output_file
                if container not in ("default", "current", ""):
                    if item.output_file:
                        base_path = os.path.splitext(item.output_file)[0]
                        item.output_file = base_path + "." + container
                    else:
                        self._generateOutputFileForItem(item)
                elif not item.output_file:
                    self._generateOutputFileForItem(item)

                # Для сохранённой команды обновляем пути в команде
                if isinstance(item.preset_name, str) and item.preset_name.startswith("cmd:"):
                    self._applyPathsToSavedCommand(item)

                # Маркируем пресет для файла: custom только если отличается от применённого пресета
                if isinstance(item.preset_name, str) and item.preset_name.startswith("cmd:"):
                    pass  # сохранённая команда имеет отдельный маркер
                elif item.preset_name and item.preset_name not in ("default", "custom"):
                    applied = self.presetManager.loadPreset(item.preset_name)
                    if applied and self._presetMatchesItem(applied, item):
                        pass  # оставляем название пресета
                    else:
                        item.preset_name = "custom"
                else:
                    default_audio = ("current", "", "default")
                    if (codec in default_like and container in default_like and resolution in default_like
                            and audio_codec in default_audio):
                        item.preset_name = "default"
                    else:
                        item.preset_name = "custom"

        # Обновляем отображение команды для выделенного файла (если один)
        self.commandManuallyEdited = False
        self.updateQueueTable()
        if len(indices) == 1 and hasattr(self.ui, "commandDisplay"):
            self.updateCommandFromGUI()
        self._updateConflictWarningsFromEditor()

    def getSelectedQueueItem(self):
        """Возвращает выделенный элемент очереди или None"""
        if self.selectedQueueIndex >= 0 and self.selectedQueueIndex < len(self.queue):
            return self.queue[self.selectedQueueIndex]
        return None

    def _presetMatchesItem(self, preset, item):
        """Сравнивает параметры пресета и QueueItem."""
        def b(v):
            return (v is True) or (str(v).strip() == "1")
        return (
            (preset.get("codec", "default") or "default") == (item.codec or "default") and
            (preset.get("container", "default") or "default") == (item.container or "default") and
            (preset.get("resolution", "default") or "default") == (item.resolution or "default") and
            (preset.get("audio_codec", "current") or "current") == (item.audio_codec or "current") and
            int(preset.get("crf", 0) or 0) == int(item.crf or 0) and
            int(preset.get("bitrate", 0) or 0) == int(item.bitrate or 0) and
            int(preset.get("fps", 0) or 0) == int(item.fps or 0) and
            int(preset.get("audio_bitrate", 0) or 0) == int(item.audio_bitrate or 0) and
            int(preset.get("sample_rate", 0) or 0) == int(item.sample_rate or 0) and
            (preset.get("preset_speed", "medium") or "medium") == (item.preset_speed or "medium") and
            (preset.get("profile_level", "") or "") == (item.profile_level or "") and
            (preset.get("pixel_format", "") or "") == (item.pixel_format or "") and
            (preset.get("tune", "") or "") == (item.tune or "") and
            int(preset.get("threads", 0) or 0) == int(item.threads or 0) and
            int(preset.get("keyint", 0) or 0) == int(item.keyint or 0) and
            b(preset.get("tag_hvc1", False)) == bool(item.tag_hvc1) and
            b(preset.get("vf_lanczos", False)) == bool(item.vf_lanczos) and
            (preset.get("extra_args", "") or "") == (item.extra_args or "")
        )

    def _getContainerExtForWarnings(self, container_value):
        if container_value in ("default", "current", "", None):
            item = self.getSelectedQueueItem()
            if item and item.file_path:
                return os.path.splitext(item.file_path)[1].lstrip(".").lower()
            return ""
        return str(container_value).lower()

    def _isTagHvc1Applicable(self, codec, container_ext):
        return container_ext in ("mp4", "mov", "m4v") and (
            codec in ("libx265", "libx266", "hevc", "h265", "copy")
        )

    def _setWidgetConflict(self, widget, on):
        if not widget:
            return
        if on:
            if widget not in self._conflictStyles:
                self._conflictStyles[widget] = widget.styleSheet()
            widget.setStyleSheet(self._conflictStyles[widget] + " border:1px solid #ff5555;")
        else:
            if widget in self._conflictStyles:
                widget.setStyleSheet(self._conflictStyles.pop(widget))

    def _clearAllConflicts(self):
        for w in list(self._conflictStyles.keys()):
            self._setWidgetConflict(w, False)

    def _updateConflictWarningsFromEditor(self):
        """Проверяет конфликты параметров и показывает предупреждение в UI."""
        if self._warningLabel is None:
            return
        codec = self._getCodecFromButtons()
        container = self._getContainerFromButtons()
        resolution = self._getResolutionFromButtons()
        audio_codec = self._getAudioCodecFromButtons()
        crf = self._crfSpin.value() if hasattr(self, "_crfSpin") else 0
        bitrate = self._bitrateSpin.value() if hasattr(self, "_bitrateSpin") else 0
        fps = self._fpsSpin.value() if hasattr(self, "_fpsSpin") else 0
        audio_bitrate = self._audioBitrateSpin.value() if hasattr(self, "_audioBitrateSpin") else 0
        sample_rate = self._sampleRateSpin.value() if hasattr(self, "_sampleRateSpin") else 0
        preset_speed = self._presetCombo.currentText() if hasattr(self, "_presetCombo") else ""
        profile_level = self._profileLevelEdit.text().strip() if hasattr(self, "_profileLevelEdit") else ""
        pixel_format = self._pixelFormatEdit.text().strip() if hasattr(self, "_pixelFormatEdit") else ""
        tune = self._tuneEdit.text().strip() if hasattr(self, "_tuneEdit") else ""
        threads = self._threadsSpin.value() if hasattr(self, "_threadsSpin") else 0
        keyint = self._keyintSpin.value() if hasattr(self, "_keyintSpin") else 0
        tag_hvc1 = self._checkTagHvc1.isChecked() if hasattr(self, "_checkTagHvc1") else False
        vf_lanczos = self._checkVfLanczos.isChecked() if hasattr(self, "_checkVfLanczos") else False

        container_ext = self._getContainerExtForWarnings(container)
        apply_tag = self._isTagHvc1Applicable(codec, container_ext)

        copy_video_conflict = (codec == "copy") and (
            vf_lanczos or resolution not in ("current", "default", "") or
            crf > 0 or bitrate > 0 or fps > 0 or preset_speed or profile_level or
            pixel_format or tune or threads > 0 or keyint > 0
        )
        copy_audio_conflict = (audio_codec in ("current", "copy")) and (audio_bitrate > 0 or sample_rate > 0)
        tag_conflict = tag_hvc1 and not apply_tag

        warnings = []
        self._clearAllConflicts()

        if tag_conflict:
            warnings.append("tag hvc1 будет проигнорирован: поддерживается только HEVC в MP4/MOV/M4V.")
            self._setWidgetConflict(self._checkTagHvc1, True)

        if copy_video_conflict:
            warnings.append("Copy видео: фильтры/CRF/битрейт/FPS/preset/keyint игнорируются.")
            for w in (self._checkVfLanczos, self._crfSpin, self._bitrateSpin, self._fpsSpin,
                      self._presetCombo, self._profileLevelEdit, self._pixelFormatEdit, self._tuneEdit,
                      self._threadsSpin, self._keyintSpin):
                self._setWidgetConflict(w, True)

        if copy_audio_conflict:
            warnings.append("Copy аудио: битрейт/частота игнорируются.")
            for w in (self._audioBitrateSpin, self._sampleRateSpin):
                self._setWidgetConflict(w, True)

        if warnings:
            self._warningLabel.setText(" | ".join(warnings))
            self._warningLabel.show()
        else:
            self._warningLabel.hide()

        # Extra args (если выбран пресет)
        if self._extraLabel is not None:
            name = self.currentPresetName or ""
            extra_text = ""
            if name and name not in ("default", "custom") and not name.startswith("cmd:"):
                preset = self.presetManager.loadPreset(name)
                extra_text = (preset or {}).get("extra_args", "") or ""
            if extra_text.strip():
                self._extraLabel.setText(f"Extra параметры пресета: {extra_text}")
                self._extraLabel.show()
            else:
                self._extraLabel.hide()
    
    def generateFFmpegCommand(self):
        """Генерирует команду FFmpeg для выделенного файла"""
        item = self.getSelectedQueueItem()
        if not item:
            return "ffmpeg"

        # Используем файл из элемента очереди
        input_file = item.file_path

        # Нормализуем входной путь
        input_file_normalized = os.path.normpath(input_file)

        # Определяем выходной файл
        container = item.container or "current"
        if container in ("default", "current", "", None):
            container_ext = os.path.splitext(input_file_normalized)[1].lstrip(".")
        else:
            container_ext = container

        if item.output_file:
            # Пользователь выбрал файл через проводник - берем базовое имя и добавляем расширение из пресета
            output_base = os.path.splitext(item.output_file)[0]
            final_output = output_base + "." + container_ext
            final_output = os.path.normpath(final_output)
            # Если файл уже существует — подбираем уникальное имя и помечаем как переименованный
            item.output_renamed = False
            if os.path.exists(final_output):
                counter = 1
                while os.path.exists(final_output):
                    final_output = output_base + "_" + str(counter) + "." + container_ext
                    final_output = os.path.normpath(final_output)
                    counter += 1
                item.output_renamed = True
            item.output_file = final_output
        else:
            # Генерируем автоматически
            input_path = os.path.dirname(input_file_normalized)
            input_base = os.path.splitext(os.path.basename(input_file_normalized))[0]

            base_output = os.path.join(input_path, input_base + "_converted")
            output_file = base_output + "." + container_ext

            # Уникальное имя выходного файла
            counter = 1
            final_output = output_file
            while os.path.exists(final_output):
                final_output = base_output + "_" + str(counter) + "." + container_ext
                counter += 1

            final_output = os.path.normpath(final_output)
            item.output_file = final_output
            item.output_renamed = False

        self.lastOutputFile = final_output
        
        # Параметры кодека:
        # - "default"/"current" => не указывать кодек (FFmpeg решит сам)
        # - "copy" => копировать видеопоток
        # - любое другое значение => использовать как -c:v <значение>
        codec = item.codec or "current"
        codec_args = []
        if codec not in ("default", "current", ""):
            codec_args = ["-c:v", codec]

        # Параметры разрешения и масштаба
        res = item.resolution or "current"
        scale = ""
        if res == "480p":
            scale = "scale=854:480"
        elif res == "720p":
            scale = "scale=1280:720"
        elif res == "1080p":
            scale = "scale=1920:1080"
        elif res == "2k":
            scale = "scale=2560:1440"
        elif res == "4k":
            scale = "scale=3840:2160"
        else:
            custom = item.custom_resolution or res
            if isinstance(custom, str) and (":" in custom or "x" in custom):
                custom = custom.replace("x", ":")
                scale = "scale=" + custom
        # Добавляем flags=lanczos к текущему масштабированию
        if getattr(item, "vf_lanczos", False):
            if scale:
                if "flags=" not in scale:
                    scale = scale + ":flags=lanczos"
            else:
                scale = "scale=iw:ih:flags=lanczos"

        vf_args = []
        if scale and codec != "copy":
            vf_args = ["-vf", scale]

        # Доп. аргументы видео (CRF, битрейт, FPS и т.д. — для любого кодека кроме copy)
        video_extra = []
        if codec != "copy":
            if getattr(item, "crf", 0) > 0:
                video_extra += ["-crf", str(item.crf)]
            if getattr(item, "bitrate", 0) > 0:
                video_extra += ["-b:v", str(item.bitrate) + "k"]
            if getattr(item, "fps", 0) > 0:
                video_extra += ["-r", str(item.fps)]
            if codec in ("libx264", "libx265", "libx266", "current", "default", "") and getattr(item, "preset_speed", ""):
                video_extra += ["-preset", item.preset_speed]
            pl = getattr(item, "profile_level", "") or ""
            if pl:
                parts_pl = pl.split(":", 1)
                video_extra += ["-profile:v", parts_pl[0]]
                if len(parts_pl) > 1:
                    video_extra += ["-level", parts_pl[1]]
            pf = getattr(item, "pixel_format", "") or ""
            if pf:
                video_extra += ["-pix_fmt", pf]
            tune_val = getattr(item, "tune", "") or ""
            if tune_val:
                video_extra += ["-tune", tune_val]
            if getattr(item, "threads", 0) > 0:
                video_extra += ["-threads", str(item.threads)]
            if getattr(item, "keyint", 0) > 0:
                video_extra += ["-g", str(item.keyint)]

        # Аудио
        ac = getattr(item, "audio_codec", "current") or "current"
        if ac == "current":
            ac = "copy"
        audio_args = ["-c:a", ac]
        if ac != "copy":
            if getattr(item, "audio_bitrate", 0) > 0:
                audio_args += ["-b:a", str(item.audio_bitrate) + "k"]
            if getattr(item, "sample_rate", 0) > 0:
                audio_args += ["-ar", str(item.sample_rate)]
        tag_hvc1 = getattr(item, "tag_hvc1", False)
        container_ext = container_ext.lower() if isinstance(container_ext, str) else ""
        apply_tag_hvc1 = tag_hvc1 and container_ext in ("mp4", "mov", "m4v") and (
            codec in ("libx265", "libx266", "hevc", "h265", "copy")
        )

        segments = self._getTrimSegments(item)
        extra_args = self._getExtraArgsList(getattr(item, "extra_args", ""))
        extra_args = self._filterExtraArgsList(extra_args, item)
        cmd_parts = ["ffmpeg"]
        if len(segments) == 1:
            start_sec, end_sec = segments[0]
            cmd_parts += ["-ss", str(start_sec), "-i", self._quotePath(input_file_normalized), "-to", str(end_sec)]
            cmd_parts += vf_args
            cmd_parts += codec_args
            cmd_parts += video_extra
            cmd_parts += audio_args
            if apply_tag_hvc1:
                cmd_parts += ["-tag:v", "hvc1"]
            if extra_args:
                cmd_parts += extra_args
        elif len(segments) > 1:
            filter_complex, _ = self._buildTrimConcatFilter(segments, scale)
            codec_display = codec if codec not in ("default", "current", "") else "libx264"
            cmd_parts += ["-i", self._quotePath(input_file_normalized), "-filter_complex", f'"{filter_complex}"', "-map", "[v]", "-map", "[outa]", "-c:v", codec_display]
            cmd_parts += video_extra
            cmd_parts += audio_args
            if apply_tag_hvc1:
                cmd_parts += ["-tag:v", "hvc1"]
            if extra_args:
                cmd_parts += extra_args
        else:
            cmd_parts += ["-i", self._quotePath(input_file_normalized)]
            cmd_parts += vf_args
            cmd_parts += codec_args
            cmd_parts += video_extra
            cmd_parts += audio_args
            if apply_tag_hvc1:
                cmd_parts += ["-tag:v", "hvc1"]
            if extra_args:
                cmd_parts += extra_args
        cmd_parts.append(self._quotePath(final_output))
        return " ".join(cmd_parts)
    
    def _generateOutputFileForItem(self, queue_item):
        """Генерирует выходной файл для элемента очереди, если он ещё не задан"""
        if not queue_item or queue_item.output_file:
            return
        
        # Используем файл из элемента очереди
        input_file = queue_item.file_path
        
        # Нормализуем входной путь
        input_file_normalized = os.path.normpath(input_file)
        
        # Определяем выходной файл на основе контейнера
        container = queue_item.container or "current"
        if container in ("default", "current", "", None):
            container_ext = os.path.splitext(input_file_normalized)[1].lstrip(".")
        else:
            container_ext = container
        
        # Генерируем автоматически
        input_path = os.path.dirname(input_file_normalized)
        input_base = os.path.splitext(os.path.basename(input_file_normalized))[0]
        
        base_output = os.path.join(input_path, input_base + "_converted")
        output_file = base_output + "." + container_ext
        
        # Уникальное имя выходного файла
        counter = 1
        final_output = output_file
        while os.path.exists(final_output):
            final_output = base_output + "_" + str(counter) + "." + container_ext
            counter += 1
        
        final_output = os.path.normpath(final_output)
        queue_item.output_file = final_output
    
    def _getFFmpegArgs(self, queue_item=None):
        """Возвращает список аргументов для запуска FFmpeg для указанного элемента очереди"""
        if queue_item is None:
            queue_item = self.getSelectedQueueItem()
        
        if not queue_item:
            return []

        # Используем файл из элемента очереди
        input_file = queue_item.file_path

        # Нормализуем входной путь
        input_file_normalized = os.path.normpath(input_file)

        # Определяем выходной файл
        container = queue_item.container or "current"
        if container in ("default", "current", "", None):
            container_ext = os.path.splitext(input_file_normalized)[1].lstrip(".")
        else:
            container_ext = container

        if queue_item.output_file:
            # Пользователь выбрал файл - берем базовое имя и добавляем расширение из пресета
            output_base = os.path.splitext(queue_item.output_file)[0]
            final_output = output_base + "." + container_ext
            final_output = os.path.normpath(final_output)
            queue_item.output_renamed = False
            if os.path.exists(final_output):
                counter = 1
                while os.path.exists(final_output):
                    final_output = output_base + "_" + str(counter) + "." + container_ext
                    final_output = os.path.normpath(final_output)
                    counter += 1
                queue_item.output_renamed = True
            queue_item.output_file = final_output
        else:
            # Генерируем автоматически
            input_path = os.path.dirname(input_file_normalized)
            input_base = os.path.splitext(os.path.basename(input_file_normalized))[0]

            base_output = os.path.join(input_path, input_base + "_converted")
            output_file = base_output + "." + container_ext

            # Уникальное имя выходного файла
            counter = 1
            final_output = output_file
            while os.path.exists(final_output):
                final_output = base_output + "_" + str(counter) + "." + container_ext
                counter += 1

            final_output = os.path.normpath(final_output)
            queue_item.output_file = final_output
            queue_item.output_renamed = False

        self.lastOutputFile = final_output
        
        # Параметры кодека
        codec = queue_item.codec or "current"
        codec_args = []
        if codec not in ("default", "current", ""):
            codec_args = ["-c:v", codec]

        # Параметры разрешения и масштаба
        res = queue_item.resolution or "current"
        scale = ""
        if res == "480p":
            scale = "scale=854:480"
        elif res == "720p":
            scale = "scale=1280:720"
        elif res == "1080p":
            scale = "scale=1920:1080"
        elif res == "2k":
            scale = "scale=2560:1440"
        elif res == "4k":
            scale = "scale=3840:2160"
        else:
            custom = queue_item.custom_resolution or res
            if isinstance(custom, str) and (":" in custom or "x" in custom):
                custom = custom.replace("x", ":")
                scale = "scale=" + custom
        # Добавляем flags=lanczos к текущему масштабированию
        if getattr(queue_item, "vf_lanczos", False):
            if scale:
                if "flags=" not in scale:
                    scale = scale + ":flags=lanczos"
            else:
                scale = "scale=iw:ih:flags=lanczos"

        vf_args = []
        if scale and codec != "copy":
            vf_args = ["-vf", scale]

        # Доп. аргументы видео (CRF, битрейт, FPS и т.д. — для любого кодека кроме copy)
        video_extra = []
        if codec != "copy":
            if getattr(queue_item, "crf", 0) > 0:
                video_extra += ["-crf", str(queue_item.crf)]
            if getattr(queue_item, "bitrate", 0) > 0:
                video_extra += ["-b:v", str(queue_item.bitrate) + "k"]
            if getattr(queue_item, "fps", 0) > 0:
                video_extra += ["-r", str(queue_item.fps)]
            if codec in ("libx264", "libx265", "libx266", "current", "default", "") and getattr(queue_item, "preset_speed", ""):
                video_extra += ["-preset", queue_item.preset_speed]
            pl = getattr(queue_item, "profile_level", "") or ""
            if pl:
                parts_pl = pl.split(":", 1)
                video_extra += ["-profile:v", parts_pl[0]]
                if len(parts_pl) > 1:
                    video_extra += ["-level", parts_pl[1]]
            pf = getattr(queue_item, "pixel_format", "") or ""
            if pf:
                video_extra += ["-pix_fmt", pf]
            tune_val = getattr(queue_item, "tune", "") or ""
            if tune_val:
                video_extra += ["-tune", tune_val]
            if getattr(queue_item, "threads", 0) > 0:
                video_extra += ["-threads", str(queue_item.threads)]
            if getattr(queue_item, "keyint", 0) > 0:
                video_extra += ["-g", str(queue_item.keyint)]

        ac = getattr(queue_item, "audio_codec", "current") or "current"
        if ac == "current":
            ac = "copy"
        audio_args = ["-c:a", ac]
        if ac != "copy":
            if getattr(queue_item, "audio_bitrate", 0) > 0:
                audio_args += ["-b:a", str(queue_item.audio_bitrate) + "k"]
            if getattr(queue_item, "sample_rate", 0) > 0:
                audio_args += ["-ar", str(queue_item.sample_rate)]
        tag_hvc1 = getattr(queue_item, "tag_hvc1", False)
        container_ext = container_ext.lower() if isinstance(container_ext, str) else ""
        apply_tag_hvc1 = tag_hvc1 and container_ext in ("mp4", "mov", "m4v") and (
            codec in ("libx265", "libx266", "hevc", "h265", "copy")
        )
        extra_args = self._getExtraArgsList(getattr(queue_item, "extra_args", ""))
        extra_args = self._filterExtraArgsList(extra_args, queue_item)

        # Сегменты обрезки/склейки
        segments = self._getTrimSegments(queue_item)
        probe_args = ["-analyzeduration", "10000000", "-probesize", "10000000"] if segments else []
        if len(segments) == 1:
            start_sec, end_sec = segments[0]
            args = probe_args + ["-ss", str(start_sec), "-i", input_file_normalized, "-to", str(end_sec)]
            args += vf_args
            args += codec_args
            args += video_extra
            args += audio_args
            if apply_tag_hvc1:
                args += ["-tag:v", "hvc1"]
            if extra_args:
                args += extra_args
            args.append(final_output)
        elif len(segments) > 1:
            filter_complex, map_v = self._buildTrimConcatFilter(segments, scale)
            codec_val = (queue_item.codec or "libx264") if (queue_item.codec and queue_item.codec not in ("default", "current", "")) else "libx264"
            args = probe_args + ["-i", input_file_normalized, "-filter_complex", filter_complex, "-map", map_v, "-map", "[outa]", "-c:v", codec_val]
            args += video_extra
            args += audio_args
            if apply_tag_hvc1:
                args += ["-tag:v", "hvc1"]
            if extra_args:
                args += extra_args
            args.append(final_output)
        else:
            args = ["-i", input_file_normalized]
            args += vf_args
            args += codec_args
            args += video_extra
            args += audio_args
            if apply_tag_hvc1:
                args += ["-tag:v", "hvc1"]
            if extra_args:
                args += extra_args
            args.append(final_output)

        return args

    def _getTrimSegments(self, queue_item):
        """Возвращает список областей обрезки (start_sec, end_sec) для элемента очереди."""
        out = list(getattr(queue_item, "keep_segments", []) or [])
        start = getattr(queue_item, "trim_start_sec", None)
        end = getattr(queue_item, "trim_end_sec", None)
        if start is not None and end is not None and end > start:
            out.append((start, end))
        return out

    def _buildTrimConcatFilter(self, segments, scale_filter):
        """Строит filter_complex для обрезки и склейки нескольких областей. Возвращает (filter_string, map_v)."""
        parts = []
        for i, (s, e) in enumerate(segments):
            parts.append(f"[0:v]trim=start={s}:end={e},setpts=PTS-STARTPTS[v{i}];[0:a]atrim=start={s}:end={e},asetpts=PTS-STARTPTS[a{i}]")
        n = len(segments)
        concat_inputs = "".join(f"[v{i}][a{i}]" for i in range(n))
        parts.append(f"{concat_inputs}concat=n={n}:v=1:a=1[outv][outa]")
        if scale_filter:
            parts.append(f"[outv]{scale_filter}[v]")
            return ";".join(parts), "[v]"
        return ";".join(parts), "[outv]"

    def startQueueProcessing(self):
        """Начинает обработку очереди файлов"""
        if not self.queue:
            QMessageBox.information(self, "Очередь", "Очередь пуста. Добавьте файлы для обработки.")
            return
        
        if self.ffmpegProcess.state() != QProcess.NotRunning:
            QMessageBox.information(self, "Ожидание", "Дождитесь завершения текущего кодирования")
            return
        
        # При новом запуске сбрасываем статусы/прогресс (чтобы можно было перекодировать повторно)
        for it in self.queue:
            it.status = QueueItem.STATUS_WAITING
            it.progress = 0
            it.error_message = ""
            it.output_renamed = False
            it.encoding_duration = 0
            it.processed_frames = 0
        # Сброс общего прогресса
        self._queueProgressMaxValue = 0
        self._queueProgressTarget = 0
        if hasattr(self.ui, 'totalQueueProgressBar'):
            self.ui.totalQueueProgressBar.setValue(0)
        # Предварительно получаем длительности/кадры для всей очереди (если возможно)
        for it in self.queue:
            self._getVideoDurationForItem(it)
        self.updateQueueTable()
        self.updateTotalQueueProgress()

        # Начинаем обработку с первого файла
        self.isPaused = False
        self._pauseStopRequested = False
        self.pausedQueueIndex = -1
        self.currentQueueIndex = 0
        self.processNextInQueue()
    
    def processNextInQueue(self):
        """Обрабатывает следующий файл в очереди"""
        if self.currentQueueIndex < 0 or self.currentQueueIndex >= len(self.queue):
            # Очередь закончена
            self.currentQueueIndex = -1
            self.updateStatus("Все файлы обработаны")
            QMessageBox.information(self, "Готово", "Обработка всех файлов завершена!")
            return
        
        item = self.queue[self.currentQueueIndex]
        
        # Обновляем статус
        item.status = QueueItem.STATUS_PROCESSING
        item.progress = 0
        self.updateQueueTable()
        self.updateStatus(f"Обработка файла {self.currentQueueIndex + 1} из {len(self.queue)}")
        
        # Проверяем, была ли команда отредактирована вручную для ЭТОГО элемента очереди.
        # Теперь это хранится внутри QueueItem, поэтому не важно, выделен он сейчас или нет.
        if getattr(item, "command_manually_edited", False) and getattr(item, "command", "").strip():
            try:
                cmd_from_item = item.command.strip()
                args = self._parseCommand(cmd_from_item)
                # Подставляем пути текущего файла (входной и выходной) в сохранённую/отредактированную команду
                args = self._substitutePathsInArgs(args, item)
            except Exception as e:
                QMessageBox.warning(
                    self,
                    "Предупреждение",
                    f"Ошибка парсинга отредактированной команды для файла:\n"
                    f"{item.file_path}\n\n{str(e)}\n\n"
                    f"Будет использована автоматически сгенерированная команда."
                )
                args = self._getFFmpegArgs(item)
        else:
            # Генерируем/получаем команду для этого файла автоматически
            args = self._getFFmpegArgs(item)
        
        if not args:
            QMessageBox.warning(self, "Ошибка", f"Не удалось сгенерировать команду для файла:\n{item.file_path}")
            item.status = QueueItem.STATUS_ERROR
            item.error_message = "Ошибка генерации команды"
            self.currentQueueIndex += 1
            self.processNextInQueue()
            return
        
        # Проверяем входной файл
        if not os.path.exists(item.file_path):
            QMessageBox.critical(self, "Ошибка", f"Файл не существует:\n{item.file_path}")
            item.status = QueueItem.STATUS_ERROR
            item.error_message = "Файл не существует"
            self.currentQueueIndex += 1
            self.processNextInQueue()
            return
        
        # Очищаем лог для нового файла
        self.ui.logDisplay.append(f"<br><b>=== Обработка файла {self.currentQueueIndex + 1}: {os.path.basename(item.file_path)} ===</b><br>")
        
        # Запускаем кодирование
        self.ui.runButton.setEnabled(False)
        if hasattr(self.ui, 'pauseResumeButton'):
            self.ui.pauseResumeButton.setEnabled(True)
            self.ui.pauseResumeButton.setText("Пауза")
        
        # Сбрасываем прогресс
        self.encodingDuration = 0
        self.currentFrame = 0
        item.processed_frames = 0
        if hasattr(self.ui, 'encodingProgressBar'):
            self.ui.encodingProgressBar.setValue(0)
        
        # Получаем длительность видео для расчёта прогресса
        self._getVideoDurationForItem(item)
        
        # Запускаем FFmpeg
        self.ffmpegProcess.start("ffmpeg", args)
    
    
    def _parseCommand(self, cmd_string):
        """Парсит строку команды в список аргументов, учитывая кавычки"""
        parts = shlex.split(cmd_string)
        # Убираем "ffmpeg" если есть
        if parts and parts[0].lower() == "ffmpeg":
            parts = parts[1:]
        return parts

    def _argsToCommand(self, args):
        """Собирает строку команды из списка аргументов."""
        def _quote_arg(arg):
            if arg is None:
                return ""
            s = str(arg)
            if not s:
                return '""'
            if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
                return s
            if any(ch.isspace() for ch in s):
                return f'"{s}"'
            return s
        return "ffmpeg " + " ".join(_quote_arg(a) for a in args)

    def _applyPathsToSavedCommand(self, item, update_display=False):
        """Подставляет актуальные пути в сохранённую команду и обновляет поле команды."""
        if not item or not getattr(item, "command", "").strip():
            return
        try:
            args = self._parseCommand(item.command)
            args = self._substitutePathsInArgs(args, item)
            new_cmd = self._argsToCommand(args)
            item.command = new_cmd
            if update_display and hasattr(self.ui, "commandDisplay"):
                cmd_widget = self.ui.commandDisplay
                cmd_widget.blockSignals(True)
                cmd_widget.setPlainText(new_cmd)
                cmd_widget.blockSignals(False)
        except Exception:
            pass

    def _getExtraArgsList(self, extra_args_str):
        """Парсит строку доп. аргументов в список для FFmpeg."""
        if not extra_args_str:
            return []
        try:
            return shlex.split(extra_args_str)
        except Exception:
            return extra_args_str.split()

    def _filterExtraArgsList(self, args, queue_item):
        """Удаляет из доп. аргументов конфликтующие флаги и явные пути вход/выход."""
        if not args:
            return []
        out = []
        skip_next_for = {"-i", "-vf", "-filter_complex", "-map", "-c:v", "-c:a", "-c", "-codec:v", "-codec:a"}
        input_path = os.path.normpath(queue_item.file_path) if queue_item else ""
        output_path = os.path.normpath(queue_item.output_file) if queue_item and queue_item.output_file else ""
        i = 0
        while i < len(args):
            token = args[i]
            if token in skip_next_for:
                i += 2
                continue
            if token in ("-y", "-an", "-vn", "-sn"):
                i += 1
                continue
            # Убираем явные пути вход/выход
            if input_path and os.path.normpath(token) == input_path:
                i += 1
                continue
            if output_path and os.path.normpath(token) == output_path:
                i += 1
                continue
            # Убираем подозрительные пути-аргументы без флага (обычно выходной файл)
            if not token.startswith("-") and "=" not in token:
                if any(sep in token for sep in ("/", "\\")) or (":" in token and len(token) > 2):
                    i += 1
                    continue
            out.append(token)
            i += 1
        return out

    def _stripInputOutputArgs(self, args):
        """Удаляет из списка аргументов первый -i <input> и последний <output>."""
        if not args:
            return []
        out = list(args)
        for i in range(len(out) - 1):
            if out[i] == "-i":
                del out[i:i + 2]
                break
        if out:
            out = out[:-1]
        return out

    def _tokenizeArgsPairs(self, args):
        """Превращает список аргументов в список пар (flag, value) с учётом флагов, принимающих значения."""
        flags_with_value = {
            "-i", "-c:v", "-c:a", "-c", "-codec:v", "-codec:a", "-b:v", "-b:a", "-r", "-crf",
            "-preset", "-profile:v", "-level", "-pix_fmt", "-tune", "-threads", "-g", "-vf",
            "-filter_complex", "-map", "-tag:v", "-ar", "-s", "-ss", "-to"
        }
        pairs = []
        i = 0
        while i < len(args):
            token = args[i]
            if token in flags_with_value and i + 1 < len(args):
                pairs.append((token, args[i + 1]))
                i += 2
            else:
                pairs.append((token, None))
                i += 1
        return pairs

    def _diffArgsPairs(self, base_pairs, user_pairs):
        """Возвращает пары аргументов, которых нет в базовой команде."""
        base = list(base_pairs)
        extra = []
        for pair in user_pairs:
            if pair in base:
                base.remove(pair)
            else:
                extra.append(pair)
        return extra

    def _extractExtraArgsFromCommands(self, base_cmd, user_cmd):
        """Сравнивает базовую команду (из UI) с командой пользователя и возвращает список доп. аргументов."""
        base_args = self._stripInputOutputArgs(self._parseCommand(base_cmd))
        user_args = self._stripInputOutputArgs(self._parseCommand(user_cmd))
        base_pairs = self._tokenizeArgsPairs(base_args)
        user_pairs = self._tokenizeArgsPairs(user_args)
        extra_pairs = self._diffArgsPairs(base_pairs, user_pairs)
        # обратно в плоский список
        extra = []
        for flag, val in extra_pairs:
            extra.append(flag)
            if val is not None:
                extra.append(val)
        return extra

    def _substitutePathsInArgs(self, args, queue_item):
        """Подставляет пути текущего файла (входной и выходной) в список аргументов. Последний аргумент — выходной файл, после первого -i — входной."""
        if not args or not queue_item:
            return args
        args = list(args)
        input_path = os.path.normpath(queue_item.file_path)
        if not queue_item.output_file:
            self._generateOutputFileForItem(queue_item)
        output_path = os.path.normpath(queue_item.output_file) if queue_item.output_file else ""
        # Замена пути после первого -i
        for i in range(len(args) - 1):
            if args[i] == "-i":
                args[i + 1] = input_path
                break
        # Замена последнего аргумента (выходной файл)
        if output_path and len(args) >= 1:
            args[-1] = output_path
        return args

    def readProcessOutput(self):
        """Читает и форматирует вывод FFmpeg с правильной цветовой схемой"""
        out = self.ffmpegProcess.readAllStandardOutput().data().decode('utf-8', errors='replace').strip()
        err = self.ffmpegProcess.readAllStandardError().data().decode('utf-8', errors='replace').strip()
        
        if out:
            self._appendLog(out, 'info')
            self._parseProgressFromLog(out)
        if err:
            self._appendLog(err, 'error')
            self._parseProgressFromLog(err)
    
    def _appendLog(self, text, source='info'):
        """Добавляет лог с правильной цветовой схемой"""
        if not text:
            return
        
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Анализируем содержимое строки для определения цвета
            color = self._determineLogColor(line, source)
            self.ui.logDisplay.append(f"<font color='{color}'>{line}</font>")
    
    def _determineLogColor(self, line, source):
        """Определяет цвет лога на основе содержимого"""
        line_lower = line.lower()
        
        # Критические ошибки - красный
        if any(keyword in line_lower for keyword in ['error', 'failed', 'cannot', 'invalid', 'unable', 'not found']):
            return 'red'
        
        # Предупреждения - жёлтый (только если действительно важно)
        if any(keyword in line_lower for keyword in ['warning', 'deprecated']):
            return '#FF8C00'  # Темно-оранжевый
        
        # Успешные сообщения - зелёный
        if any(keyword in line_lower for keyword in ['success', 'complete', 'done', 'finished']):
            return 'green'
        
        # Прогресс и статистика - синий
        if any(keyword in line_lower for keyword in ['frame=', 'fps=', 'bitrate=', 'time=', 'size=']):
            return '#0066CC'  # Синий
        
        # Информационные сообщения от FFmpeg (stderr, но не ошибки) - чёрный
        # FFmpeg выводит много информации в stderr, но это не ошибки
        if source == 'error':
            # Проверяем, не является ли это просто информационным сообщением
            if any(keyword in line_lower for keyword in ['stream', 'video:', 'audio:', 'duration:', 'input', 'output']):
                return 'black'
            # Если это не информационное, но и не явная ошибка - серый
            if not any(keyword in line_lower for keyword in ['error', 'failed']):
                return '#666666'  # Серый для обычных сообщений stderr
        
        # По умолчанию - чёрный для stdout, серый для stderr
        return 'black' if source == 'info' else '#666666'
    
    def _parseProgressFromLog(self, line):
        """Парсит прогресс кодирования из логов FFmpeg"""
        if self.currentQueueIndex < 0 or self.currentQueueIndex >= len(self.queue):
            return
        
        item = self.queue[self.currentQueueIndex]
        
        # Парсим frame
        frame_match = re.search(r'frame=\s*(\d+)', line)
        if frame_match:
            self.currentFrame = int(frame_match.group(1))
            try:
                prev = getattr(item, "processed_frames", 0) or 0
                item.processed_frames = max(prev, self.currentFrame)
            except Exception:
                item.processed_frames = self.currentFrame
        
        # Парсим time (время кодирования)
        time_match = re.search(r'time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})', line)
        if time_match:
            hours = int(time_match.group(1))
            minutes = int(time_match.group(2))
            seconds = int(time_match.group(3))
            centiseconds = int(time_match.group(4))
            self.encodingDuration = hours * 3600 + minutes * 60 + seconds + centiseconds / 100.0
            item.encoding_duration = self.encodingDuration
        
        # Обновляем прогресс
        self.updateEncodingProgress()
    
    def updateEncodingProgress(self):
        """Обновляет прогресс-бар и таймлайн на основе текущего прогресса"""
        if self.currentQueueIndex < 0 or self.currentQueueIndex >= len(self.queue):
            return
        
        item = self.queue[self.currentQueueIndex]
        
        if item.video_duration > 0 and self.encodingDuration > 0:
            # Вычисляем процент прогресса
            progress = min(100, int((self.encodingDuration / item.video_duration) * 100))
            self.encodingProgress = progress
            item.progress = progress
            
            # Обновляем прогресс-бар
            if hasattr(self.ui, 'encodingProgressBar'):
                self.ui.encodingProgressBar.setValue(progress)
            
            # Обновляем прогресс в таблице
            if hasattr(self.ui, 'queueTableWidget'):
                table = self.ui.queueTableWidget
                if self.currentQueueIndex < table.rowCount():
                    progress_item = table.item(self.currentQueueIndex, 3)
                    if progress_item:
                        progress_item.setText(f"{progress}%")
            
            # Обновляем таймлайн предпросмотра (если есть)
            if hasattr(self.ui, 'videoTimelineSlider') and item.video_duration > 0:
                # Обновляем только если не происходит ручная перемотка
                if not self.ui.videoTimelineSlider.isSliderDown():
                    max_value = self.ui.videoTimelineSlider.maximum()
                    timeline_position = int((self.encodingDuration / item.video_duration) * max_value)
                    self.ui.videoTimelineSlider.setValue(timeline_position)

        # Общий прогресс обновляем постоянно из логов
        self.updateTotalQueueProgress()

    def updateTotalQueueProgress(self):
        """Обновляет общий прогресс-бар для всей очереди файлов."""
        if not self.queue or not hasattr(self.ui, 'totalQueueProgressBar'):
            return
        # 1) Прогресс по кадрам (если для всех файлов известны total_frames)
        have_frames = all(getattr(it, "total_frames", 0) > 0 for it in self.queue)
        total_frames = sum(getattr(it, "total_frames", 0) or 0 for it in self.queue) if have_frames else 0
        if total_frames > 0:
            done_frames = 0
            for it in self.queue:
                if it.status == QueueItem.STATUS_SUCCESS:
                    done_frames += getattr(it, "total_frames", 0) or 0
            if self.currentQueueIndex >= 0 and self.currentQueueIndex < len(self.queue):
                current_item = self.queue[self.currentQueueIndex]
                if current_item.status == QueueItem.STATUS_PROCESSING:
                    cur_total = getattr(current_item, "total_frames", 0) or 0
                    cur_done = getattr(current_item, "processed_frames", 0) or 0
                    if cur_total > 0:
                        done_frames += min(cur_done, cur_total)
            percentage = int(min(100.0, (done_frames / total_frames) * 100))
            self._setQueueProgressTarget(percentage)
            return

        # 2) Фолбэк: прогресс по длительности
        total_duration = sum(max(0.0, getattr(it, "video_duration", 0) or 0) for it in self.queue)
        if total_duration > 0:
            done = 0.0
            for it in self.queue:
                if it.status == QueueItem.STATUS_SUCCESS:
                    done += max(0.0, getattr(it, "video_duration", 0) or 0)
            if self.currentQueueIndex >= 0 and self.currentQueueIndex < len(self.queue):
                current_item = self.queue[self.currentQueueIndex]
                if current_item.status == QueueItem.STATUS_PROCESSING:
                    cur_dur = max(0.0, getattr(current_item, "video_duration", 0) or 0)
                    cur_time = max(0.0, getattr(current_item, "encoding_duration", 0) or 0)
                    if cur_dur > 0:
                        done += min(cur_time, cur_dur)
            percentage = int(min(100.0, (done / total_duration) * 100))
            self._setQueueProgressTarget(percentage)
            return

        # 3) Фолбэк: по количеству файлов
        total_files = len(self.queue)
        completed_files = sum(1 for item in self.queue if item.status == QueueItem.STATUS_SUCCESS)
        current_progress = 0
        if self.currentQueueIndex >= 0 and self.currentQueueIndex < len(self.queue):
            current_item = self.queue[self.currentQueueIndex]
            if current_item.status == QueueItem.STATUS_PROCESSING:
                current_progress = current_item.progress
        total_progress = completed_files * 100 + current_progress
        max_progress = total_files * 100
        self._setQueueProgressTarget(int(total_progress / max_progress * 100) if max_progress > 0 else 0)

    def _setQueueProgressTarget(self, value):
        if not hasattr(self.ui, 'totalQueueProgressBar'):
            return
        value = max(0, min(100, int(value)))
        self._queueProgressMaxValue = max(getattr(self, "_queueProgressMaxValue", 0), value)
        self._queueProgressTarget = self._queueProgressMaxValue
        if not self._queueProgressTimer.isActive():
            self._queueProgressTimer.start(50)

    def _tickQueueProgress(self):
        if not hasattr(self.ui, 'totalQueueProgressBar'):
            self._queueProgressTimer.stop()
            return
        if self._queueProgressTarget is None:
            self._queueProgressTimer.stop()
            return
        current = self.ui.totalQueueProgressBar.value()
        target = self._queueProgressTarget
        if current == target:
            self._queueProgressTimer.stop()
            return
        step = 2 if abs(target - current) > 3 else 1
        if current < target:
            current = min(target, current + step)
        else:
            current = max(target, current - step)
        self.ui.totalQueueProgressBar.setValue(current)
    
    def loadVideoForPreview(self):
        """Загружает видео в медиаплеер для предпросмотра"""
        item = self.getSelectedQueueItem()
        if not self.mediaPlayer or not item:
            return
        
        try:
            # Загружаем видео из выделенного элемента очереди
            url = QUrl.fromLocalFile(item.file_path)
            self.mediaPlayer.setSource(url)
            
            # Обновляем inputFile для обратной совместимости
            self.inputFile = item.file_path
            
            # Получаем длительность видео (будет установлена асинхронно)
            # Обновим таймлайн когда длительность станет известна
        except Exception as e:
            print(f"Ошибка загрузки видео: {e}")
    
    def toggleVideoPlayback(self):
        """Переключает воспроизведение/паузу видео"""
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
    
    def stopVideo(self):
        """Останавливает воспроизведение видео"""
        if not self.mediaPlayer:
            return
        self.mediaPlayer.stop()
        if hasattr(self.ui, 'videoPlayButton'):
            self.ui.videoPlayButton.setText("Play")

    # Шаг на один кадр (~33 мс при 30 fps)
    FRAME_STEP_MS = 33

    def stepVideoPreviousFrame(self):
        """Переход на предыдущий кадр"""
        if not self.mediaPlayer or self.videoDuration <= 0:
            return
        pos_ms = self.mediaPlayer.position()
        self.mediaPlayer.setPosition(max(0, pos_ms - self.FRAME_STEP_MS))

    def stepVideoNextFrame(self):
        """Переход на следующий кадр"""
        if not self.mediaPlayer or self.videoDuration <= 0:
            return
        pos_ms = self.mediaPlayer.position()
        duration_ms = int(self.videoDuration * 1000)
        self.mediaPlayer.setPosition(min(duration_ms, pos_ms + self.FRAME_STEP_MS))

    def setTrimStart(self):
        """Поставить начало оставляемого промежутка (In) на текущем кадре"""
        item = self.getSelectedQueueItem()
        if not item or not self.mediaPlayer:
            return
        item.trim_start_sec = self.mediaPlayer.position() / 1000.0
        self._updateTrimSegmentBar()

    def setTrimEnd(self):
        """Поставить конец оставляемого промежутка (Out) на текущем кадре"""
        item = self.getSelectedQueueItem()
        if not item or not self.mediaPlayer:
            return
        item.trim_end_sec = self.mediaPlayer.position() / 1000.0
        self._updateTrimSegmentBar()

    def addKeepArea(self):
        """Добавить текущую область (in–out) в список областей склейки"""
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
        """Краткие подсказки при наведении на кнопки плеера"""
        tooltips = {
            "videoPlayButton": "Воспроизведение / пауза",
            "PreviousFrame": "Предыдущий кадр",
            "NextFrame": "Следующий кадр",
            "videoTimelineSlider": "Перемотка по времени",
            "videoTimeLabel": "",  # не трогаем
            "videoMuteButton": "Вкл/выкл звук",
            "AddKeepArea": "Добавить область склейки (текущий in–out)",
            "SetInPoint": "Поставить начало оставляемого промежутка (In) на текущем кадре",
            "SetOutPoint": "Поставить конец оставляемого промежутка (Out) на текущем кадре",
        }
        for name, text in tooltips.items():
            if text and hasattr(self.ui, name):
                getattr(self.ui, name).setToolTip(text)
    
    def toggleVideoMute(self):
        """Переключает звук видео"""
        if not self.audioOutput:
            return
        
        self.isMuted = not self.isMuted
        self.audioOutput.setMuted(self.isMuted)
        
        if hasattr(self.ui, 'videoMuteButton'):
            self.ui.videoMuteButton.setText("🔇" if self.isMuted else "🔊")
    
    def seekVideo(self, position):
        """Перематывает видео на указанную позицию"""
        if not self.mediaPlayer or self.videoDuration <= 0:
            return
        
        # Преобразуем позицию слайдера в миллисекунды
        max_value = self.ui.videoTimelineSlider.maximum()
        time_ms = int((position / max_value) * self.videoDuration * 1000)
        self.mediaPlayer.setPosition(time_ms)
    
    def pauseVideoForSeek(self):
        """Временно ставит видео на паузу при перемотке"""
        if not self.mediaPlayer:
            return
        
        # Сохраняем состояние воспроизведения
        self.wasPlayingBeforeSeek = (self.mediaPlayer.playbackState() == QMediaPlayer.PlayingState)
        if self.wasPlayingBeforeSeek:
            self.mediaPlayer.pause()
    
    def resumeVideoAfterSeek(self):
        """Возобновляет воспроизведение после перемотки"""
        if not self.mediaPlayer:
            return
        
        if hasattr(self, 'wasPlayingBeforeSeek') and self.wasPlayingBeforeSeek:
            self.mediaPlayer.play()

    def eventFilter(self, obj, event):
        """Клик по таймлайну — перемотка в указанное место (не только перетаскивание)."""
        spin_set = getattr(self, "_spinSelectAllOnFocus", set())
        if event.type() in (QEvent.FocusIn, QEvent.MouseButtonPress):
            # Выделение текста в QSpinBox при клике/фокусе
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
        """Обработчик изменения длительности видео"""
        self.videoDuration = duration / 1000.0  # Конвертируем в секунды
        
        # Обновляем максимальное значение слайдера
        if hasattr(self.ui, 'videoTimelineSlider'):
            self.ui.videoTimelineSlider.setMaximum(1000)
        
        # Обновляем отображение времени
        self.updateVideoTime()
        # Полоска обрезки использует длительность текущего видео — обновить под выбранный файл
        self._updateTrimSegmentBar()
    
    def onVideoPositionChanged(self, position):
        """Обработчик изменения позиции видео"""
        if not hasattr(self.ui, 'videoTimelineSlider') or self.videoDuration <= 0:
            return
        
        # Обновляем слайдер только если не происходит ручная перемотка
        if not self.ui.videoTimelineSlider.isSliderDown():
            max_value = self.ui.videoTimelineSlider.maximum()
            slider_position = int((position / 1000.0 / self.videoDuration) * max_value)
            self.ui.videoTimelineSlider.setValue(slider_position)
    
    def onVideoPlaybackStateChanged(self, state):
        """Обработчик изменения состояния воспроизведения"""
        if hasattr(self.ui, 'videoPlayButton'):
            if state == QMediaPlayer.PlayingState:
                self.ui.videoPlayButton.setText("Pause")
            else:
                self.ui.videoPlayButton.setText("Play")
    
    def updateVideoTime(self):
        """Обновляет отображение времени видео"""
        if not hasattr(self.ui, 'videoTimeLabel') or not self.mediaPlayer:
            return
        
        current_pos = self.mediaPlayer.position() / 1000.0  # в секундах
        duration = self.videoDuration
        
        current_str = self._formatTime(current_pos)
        duration_str = self._formatTime(duration)
        
        self.ui.videoTimeLabel.setText(f"{current_str} / {duration_str}")
    
    def _formatTime(self, seconds):
        """Форматирует время в формат MM:SS или HH:MM:SS"""
        if seconds < 0:
            seconds = 0
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"
    
    def togglePauseEncoding(self):
        """Переключает паузу/возобновление кодирования"""
        # Если мы в "паузе" — это режим ожидания возобновления очереди
        if self.isPaused:
            self.resumeEncoding()
            return

        # Если процесса нет — паузить нечего
        if not self.ffmpegProcess or self.ffmpegProcess.state() == QProcess.NotRunning:
            return

        self.pauseEncoding()
    
    def pauseEncoding(self):
        """Останавливает очередь (по ТЗ): отменяет текущий и последующие файлы."""
        if self.ffmpegProcess.state() != QProcess.Running:
            return
        
        if self.currentQueueIndex < 0 or self.currentQueueIndex >= len(self.queue):
            return
        
        item = self.queue[self.currentQueueIndex]
        self.isPaused = True
        self._pauseStopRequested = True
        self.pausedQueueIndex = self.currentQueueIndex

        # Отменяем текущий файл и все следующие (возвращаем в ожидание)
        for i in range(self.currentQueueIndex, len(self.queue)):
            self.queue[i].status = QueueItem.STATUS_WAITING
            self.queue[i].progress = 0
            self.queue[i].error_message = ""
        
        # Пытаемся приостановить процесс через сигналы
        try:
            if platform.system() == "Windows":
                # На Windows останавливаем процесс. Дальше будем возобновлять
                # с файла, который был активен в момент остановки.
                self.ffmpegProcess.kill()
            else:
                # На Linux/Mac используем SIGSTOP
                import signal
                try:
                    os.kill(self.ffmpegProcess.processId(), signal.SIGSTOP)
                except (ProcessLookupError, PermissionError) as e:
                    QMessageBox.warning(self, "Ошибка", 
                        f"Не удалось приостановить процесс: {str(e)}")
                    self.isPaused = False
                    item.status = QueueItem.STATUS_PROCESSING
                    return
        except Exception as e:
            QMessageBox.warning(self, "Предупреждение", 
                f"Ошибка при паузе: {str(e)}")
            self.isPaused = False
            item.status = QueueItem.STATUS_PROCESSING
            return
        
        # Обновляем таблицу
        self.updateQueueTable()
        self.updateTotalQueueProgress()
        
        if hasattr(self.ui, 'pauseResumeButton'):
            self.ui.pauseResumeButton.setText("Возобновить")
        # Разрешаем нажимать "возобновить" (run остаётся выключенным как и при обычном процессе)
        self.updateStatus("Остановлено. Нажмите ▶ Возобновить для продолжения.")
    
    def resumeEncoding(self):
        """Возобновляет очередь с файла, который был активен при остановке."""
        if not self.isPaused:
            return

        if self.pausedQueueIndex < 0 or self.pausedQueueIndex >= len(self.queue):
            QMessageBox.warning(self, "Ошибка", "Не удалось определить файл для возобновления")
            self.isPaused = False
            self._pauseStopRequested = False
            return

        # Удаляем уже созданный/частично созданный файл, чтобы ffmpeg не завис на запросе overwrite
        item = self.queue[self.pausedQueueIndex]
        if item.output_file and os.path.exists(item.output_file):
            try:
                os.remove(item.output_file)
            except Exception:
                # Если не смогли удалить — всё равно попробуем продолжить, но ffmpeg может спросить overwrite
                pass

        self.isPaused = False
        self._pauseStopRequested = False
        self.currentQueueIndex = self.pausedQueueIndex

        if hasattr(self.ui, 'pauseResumeButton'):
            self.ui.pauseResumeButton.setText("Пауза")

        # Запускаем очередь заново с нужного файла
        self.processNextInQueue()

    def _getVideoDuration(self):
        """Получает длительность видео через FFprobe"""
        item = self.getSelectedQueueItem()
        if item:
            self._getVideoDurationForItem(item)

    # ===== Перемещение файлов в очереди (кнопки QueueUp/QueueDown) =====

    def _moveQueueItem(self, from_index, to_index):
        """Перемещает элемент очереди и обновляет таблицу/выделение."""
        if from_index == to_index:
            return
        if from_index < 0 or from_index >= len(self.queue):
            return
        if to_index < 0 or to_index >= len(self.queue):
            return

        self.queue.insert(to_index, self.queue.pop(from_index))

        # Обновляем индексы текущего файла, если нужно
        if self.currentQueueIndex == from_index:
            self.currentQueueIndex = to_index
        elif from_index < self.currentQueueIndex <= to_index:
            self.currentQueueIndex -= 1
        elif to_index <= self.currentQueueIndex < from_index:
            self.currentQueueIndex += 1

        self.updateQueueTable()

        # Перевыделяем строку
        if hasattr(self.ui, 'queueTableWidget'):
            table = self.ui.queueTableWidget
            table.blockSignals(True)
            table.clearSelection()
            table.selectRow(to_index)
            table.blockSignals(False)
        self.selectedQueueIndex = to_index

    def moveQueueItemUp(self):
        """Поднять выделенный файл в очереди выше."""
        table = self.ui.queueTableWidget if hasattr(self.ui, 'queueTableWidget') else None
        if not table:
            return
        selected_rows = table.selectionModel().selectedRows()
        if len(selected_rows) != 1:
            return
        row = selected_rows[0].row()
        if row <= 0:
            return
        self._moveQueueItem(row, row - 1)

    def moveQueueItemDown(self):
        """Опустить выделенный файл в очереди ниже."""
        table = self.ui.queueTableWidget if hasattr(self.ui, 'queueTableWidget') else None
        if not table:
            return
        selected_rows = table.selectionModel().selectedRows()
        if len(selected_rows) != 1:
            return
        row = selected_rows[0].row()
        if row >= len(self.queue) - 1:
            return
        self._moveQueueItem(row, row + 1)
    
    def _getVideoDurationForItem(self, item):
        """Получает длительность видео для элемента очереди"""
        if not item or not item.file_path:
            return
        
        try:
            import subprocess
            # Определяем путь к ffprobe:
            # 1. Если в корне проекта лежит ffprobe(.exe) — используем его
            # 2. Иначе пробуем вызвать просто "ffprobe" из PATH
            ffprobe_executable = "ffprobe"
            try:
                base_dir = os.path.dirname(os.path.abspath(__file__))
                if platform.system() == "Windows":
                    local_ffprobe = os.path.join(base_dir, "ffprobe.exe")
                else:
                    local_ffprobe = os.path.join(base_dir, "ffprobe")
                if os.path.exists(local_ffprobe):
                    ffprobe_executable = local_ffprobe
            except Exception:
                # Если что‑то пошло не так при определении пути, просто используем "ffprobe"
                pass

            # Используем ffprobe для получения длительности/кадров
            cmd = [
                ffprobe_executable, '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'format=duration:stream=avg_frame_rate,nb_frames',
                '-of', 'json',
                item.file_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                data = {}
                try:
                    data = json.loads(result.stdout or "{}")
                except Exception:
                    data = {}
                duration_str = (data.get("format") or {}).get("duration", "") or ""
                if duration_str:
                    item.video_duration = float(duration_str)
                    self.videoDuration = item.video_duration
                # FPS и кол-во кадров
                streams = data.get("streams") or []
                if streams:
                    stream = streams[0] or {}
                    fps_str = stream.get("avg_frame_rate", "") or ""
                    nb_frames_str = stream.get("nb_frames", "") or ""
                    fps_val = 0.0
                    if fps_str and fps_str != "0/0":
                        if "/" in fps_str:
                            num, den = fps_str.split("/", 1)
                            try:
                                den_val = float(den)
                                fps_val = float(num) / den_val if den_val else 0.0
                            except Exception:
                                fps_val = 0.0
                        else:
                            try:
                                fps_val = float(fps_str)
                            except Exception:
                                fps_val = 0.0
                    item.video_fps = fps_val
                    total_frames = 0
                    if nb_frames_str and str(nb_frames_str).isdigit():
                        total_frames = int(nb_frames_str)
                    elif item.video_duration > 0 and fps_val > 0:
                        total_frames = int(item.video_duration * fps_val)
                    if total_frames > 0:
                        item.total_frames = total_frames
        except FileNotFoundError:
            # ffprobe не найден — не считаем это критической ошибкой, просто
            # отключаем прогресс по длительности для этого файла.
            print(
                "Не удалось получить длительность видео: ffprobe не найден. "
                "Убедитесь, что ffprobe доступен в PATH или лежит рядом с ffmpeg.exe."
            )
        except Exception as e:
            print(f"Не удалось получить длительность видео: {e}")
    
    def processFinished(self, exitCode, exitStatus):
        if self.currentQueueIndex < 0 or self.currentQueueIndex >= len(self.queue):
            return
        
        item = self.queue[self.currentQueueIndex]

        # Если мы остановили очередь через кнопку "Пауза",
        # то это НЕ ошибка файла — мы отменили обработку.
        if self.isPaused and self._pauseStopRequested:
            # Удаляем недокодированный файл при паузе/отмене
            try:
                if item.output_file and os.path.exists(item.output_file):
                    os.remove(item.output_file)
            except Exception:
                pass
            self.ui.runButton.setEnabled(True)
            if hasattr(self.ui, 'pauseResumeButton'):
                self.ui.pauseResumeButton.setEnabled(True)
            self.updateQueueTable()
            self.updateTotalQueueProgress()
            return
        
        # Обновляем статус текущего файла
        if exitCode == 0:
            item.status = QueueItem.STATUS_SUCCESS
            item.progress = 100
            if getattr(item, "total_frames", 0):
                item.processed_frames = item.total_frames
            self.ui.logDisplay.append(f"<br><b><font color='green'>✓ Файл обработан успешно: {os.path.basename(item.file_path)}</font></b>")
        else:
            item.status = QueueItem.STATUS_ERROR
            item.error_message = f"Код завершения: {exitCode}"
            self.ui.logDisplay.append(f"<br><b><font color='red'>✗ Ошибка обработки файла: {os.path.basename(item.file_path)} (код: {exitCode})</font></b>")
            # Удаляем битый/частично созданный файл
            try:
                if item.output_file and os.path.exists(item.output_file):
                    os.remove(item.output_file)
            except Exception:
                pass
        
        # Обновляем таблицу
        self.updateQueueTable()
        self.updateTotalQueueProgress()
        
        # Обновляем прогресс-бар
        if hasattr(self.ui, 'encodingProgressBar'):
            self.ui.encodingProgressBar.setValue(100 if exitCode == 0 else 0)
        
        # Отключаем кнопку паузы
        if hasattr(self.ui, 'pauseResumeButton'):
            self.ui.pauseResumeButton.setEnabled(False)
            self.ui.pauseResumeButton.setText("Пауза")
        
        self.isPaused = False
        
        # Переходим к следующему файлу
        self.currentQueueIndex += 1
        if self.currentQueueIndex < len(self.queue):
            # Небольшая задержка перед следующим файлом
            QTimer.singleShot(500, self.processNextInQueue)
        else:
            # Все файлы обработаны
            self.currentQueueIndex = -1
            self.ui.runButton.setEnabled(True)
            self.updateStatus("Все файлы обработаны")
            if hasattr(self.ui, 'openOutputFolderButton'):
                self.ui.openOutputFolderButton.setEnabled(True)
    
    def updateStatus(self, status_text):
        """Обновляет статус в статусбаре"""
        self.ui.statusbar.showMessage(status_text)
    
    def openOutputFolder(self):
        """Открывает папку с выходным файлом в проводнике/файловом менеджере"""
        target_file = ""
        item = self.getSelectedQueueItem()
        if item and item.output_file:
            target_file = item.output_file
        elif self.lastOutputFile:
            target_file = self.lastOutputFile
        if not target_file:
            QMessageBox.warning(self, "Ошибка", "Выходной файл не найден")
            return
        output_dir = os.path.dirname(target_file)
        if not os.path.exists(output_dir):
            QMessageBox.warning(self, "Ошибка", f"Папка не существует:\n{output_dir}")
            return

        if platform.system() == "Windows":
            if os.path.exists(target_file):
                os.system(f'explorer /select,"{target_file}"')
            else:
                os.startfile(output_dir)
        elif platform.system() == "Darwin":  # macOS
            if os.path.exists(target_file):
                os.system(f'open -R "{target_file}"')
            else:
                os.system(f'open "{output_dir}"')
        else:  # Linux
            os.system(f'xdg-open "{output_dir}"')


    # ===== Новые методы создания/сохранения пресетов через редактор =====

    def _getPresetExtraFromUI(self):
        """Собирает из редактора пресетов все доп. параметры (CRF, битрейт, FPS и т.д.) для сохранения в пресет."""
        def spin_val(attr, default=0):
            w = getattr(self, attr, None)
            return w.value() if w is not None else default
        def text_val(attr, default=""):
            w = getattr(self, attr, None)
            return w.text().strip() if w is not None else default
        def combo_text(attr, default=""):
            w = getattr(self, attr, None)
            return w.currentText() if w is not None else default
        def check_val(attr, default=False):
            w = getattr(self, attr, None)
            return w.isChecked() if w is not None else default
        return {
            "audio_codec": self._getAudioCodecFromButtons(),
            "crf": spin_val("_crfSpin"),
            "bitrate": spin_val("_bitrateSpin"),
            "fps": spin_val("_fpsSpin"),
            "audio_bitrate": spin_val("_audioBitrateSpin"),
            "sample_rate": spin_val("_sampleRateSpin"),
            "preset_speed": combo_text("_presetCombo", "medium"),
            "profile_level": text_val("_profileLevelEdit"),
            "pixel_format": text_val("_pixelFormatEdit"),
            "tune": text_val("_tuneEdit"),
            "threads": spin_val("_threadsSpin"),
            "keyint": spin_val("_keyintSpin"),
            "tag_hvc1": check_val("_checkTagHvc1"),
            "vf_lanczos": check_val("_checkVfLanczos"),
        }

    def _generateCommandWithoutExtra(self):
        """Генерирует команду из текущих настроек без extra_args пресета."""
        item = self.getSelectedQueueItem()
        if not item:
            return ""
        saved_extra = getattr(item, "extra_args", "")
        item.extra_args = ""
        cmd = self.generateFFmpegCommand()
        item.extra_args = saved_extra
        return cmd

    def createPreset(self):
        """Создаёт новый пресет на основе текущих настроек редактора пресетов (включая CRF, битрейт, FPS и т.д.)."""
        codec = self._getCodecFromButtons()
        container = self._getContainerFromButtons()
        resolution = self._getResolutionFromButtons()

        name, ok = QInputDialog.getText(self, "Создать пресет", "Имя пресета:")
        if not ok or not name.strip():
            return
        name = name.strip()

        desc, ok = QInputDialog.getMultiLineText(self, "Описание пресета", "Описание (необязательно):")
        if not ok:
            return

        extra = self._getPresetExtraFromUI()
        self.presetManager.savePreset(name, codec, resolution, container, desc.strip(), insert_at_top=True, **extra)
        self.currentPresetName = name
        self.refreshPresetsTable()

    def saveCurrentPreset(self):
        """Сохраняет изменения в текущий выбранный пресет (включая все настройки: CRF, битрейт, FPS и т.д.)."""
        codec = self._getCodecFromButtons()
        container = self._getContainerFromButtons()
        resolution = self._getResolutionFromButtons()

        name = self.currentPresetName
        if not name or name == "custom":
            name, ok = QInputDialog.getText(self, "Сохранить пресет", "Имя пресета:")
            if not ok or not name.strip():
                return
            name = name.strip()

        desc = ""
        existing = self.presetManager.loadPreset(name)
        if existing and existing.get("description"):
            desc = existing["description"]

        extra = self._getPresetExtraFromUI()
        self.presetManager.savePreset(name, codec, resolution, container, desc, **extra)
        self.currentPresetName = name
        self.refreshPresetsTable()

    def savePresetWithCustomParams(self):
        """Сохраняет пресет и доп. параметры, которые пользователь вручную добавил в команду FFmpeg."""
        item = self.getSelectedQueueItem()
        if not item:
            QMessageBox.information(self, "Сохранить пресет", "Сначала выберите файл в очереди.")
            return

        if not hasattr(self.ui, "commandDisplay"):
            return
        user_cmd = self.ui.commandDisplay.toPlainText().strip()
        if not user_cmd or user_cmd.lower() == "ffmpeg":
            QMessageBox.information(self, "Сохранить пресет", "Команда пуста. Сначала задайте параметры или отредактируйте команду.")
            return

        base_cmd = self._generateCommandWithoutExtra()
        extra_args_list = self._extractExtraArgsFromCommands(base_cmd, user_cmd)
        extra_args = " ".join(extra_args_list).strip()

        codec = self._getCodecFromButtons()
        container = self._getContainerFromButtons()
        resolution = self._getResolutionFromButtons()

        name = self.currentPresetName
        if not name or name == "custom":
            name, ok = QInputDialog.getText(self, "Сохранить пресет", "Имя пресета:")
            if not ok or not name.strip():
                return
            name = name.strip()

        desc = ""
        existing = self.presetManager.loadPreset(name)
        if existing and existing.get("description"):
            desc = existing["description"]

        extra = self._getPresetExtraFromUI()
        extra["extra_args"] = extra_args
        self.presetManager.savePreset(name, codec, resolution, container, desc, **extra)
        self.currentPresetName = name
        self.refreshPresetsTable()
        QMessageBox.information(self, "Сохранено", "Пресет сохранён с дополнительными параметрами.")

    def copyCommand(self):
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(self.ui.commandDisplay.toPlainText())
        # Убираем модальное сообщение — копирование тихое

    def _chooseDataType(self, title):
        """Выбор типа данных для импорта/экспорта."""
        items = ["Пресеты", "Команды FFmpeg", "Кастомные параметры"]
        choice, ok = QInputDialog.getItem(self, title, "Что импортировать/экспортировать:", items, 0, False)
        if not ok or not choice:
            return None
        if choice == "Пресеты":
            return "presets"
        if choice == "Команды FFmpeg":
            return "commands"
        return "custom"

    def exportData(self):
        """Экспорт: пользователь выбирает тип данных и место сохранения файла."""
        dtype = self._chooseDataType("Экспорт")
        if not dtype:
            return
        if dtype == "presets":
            source = self.presetManager.presets_file
            filter_str = "XML файлы (*.xml)"
        elif dtype == "commands":
            source = self._savedCommandsPath
            filter_str = "JSON файлы (*.json)"
        else:
            source = self._customOptionsPath
            filter_str = "JSON файлы (*.json)"

        if not os.path.exists(source):
            QMessageBox.information(self, "Экспорт", "Файл не найден. Сначала создайте данные в программе.")
            return

        default_name = os.path.basename(source)
        file_path, _ = QFileDialog.getSaveFileName(self, "Экспорт", default_name, filter_str)
        if not file_path:
            return
        try:
            shutil.copyfile(source, file_path)
            QMessageBox.information(self, "Экспорт", f"Файл сохранён:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Экспорт", f"Не удалось сохранить файл:\n{str(e)}")

    def importData(self):
        """Импорт: пользователь выбирает тип данных, затем файл для импорта."""
        dtype = self._chooseDataType("Импорт")
        if not dtype:
            return
        if dtype == "presets":
            file_path, _ = QFileDialog.getOpenFileName(self, "Импорт пресетов", "", "XML файлы (*.xml)")
            if not file_path:
                return
            ok = self.presetManager.mergePresetsFromFile(file_path)
            if ok:
                QMessageBox.information(self, "Импорт", "Пресеты импортированы (слияние выполнено).")
                self.refreshPresetsTable()
            else:
                QMessageBox.critical(self, "Импорт", "Не удалось импортировать пресеты.")
            return
        if dtype == "commands":
            file_path, _ = QFileDialog.getOpenFileName(self, "Импорт команд", "", "JSON файлы (*.json)")
            if not file_path:
                return
            ok = self._mergeSavedCommandsFromFile(file_path)
            if ok:
                QMessageBox.information(self, "Импорт", "Команды импортированы.")
            else:
                QMessageBox.critical(self, "Импорт", "Не удалось импортировать команды.")
            return
        # custom params
        file_path, _ = QFileDialog.getOpenFileName(self, "Импорт пользовательских параметров", "", "JSON файлы (*.json)")
        if not file_path:
            return
        ok = self._mergeCustomOptionsFromFile(file_path)
        if ok:
            QMessageBox.information(self, "Импорт", "Параметры импортированы.")
        else:
            QMessageBox.critical(self, "Импорт", "Не удалось импортировать параметры.")

    def _mergeSavedCommandsFromFile(self, file_path):
        """Сливает команды FFmpeg из файла JSON, не перезаписывая существующие имена."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            incoming = data.get("commands", [])
            if not isinstance(incoming, list):
                return False
            existing = self._loadSavedCommands()
            names = {c.get("name") for c in existing}
            for cmd in incoming:
                if not isinstance(cmd, dict):
                    continue
                name = cmd.get("name")
                command = cmd.get("command")
                if not name or command is None:
                    continue
                if name in names:
                    continue
                existing.append({"name": name, "command": command})
                names.add(name)
            self._saveSavedCommands(existing)
            return True
        except Exception:
            return False

    def _mergeCustomOptionsFromFile(self, file_path):
        """Сливает кастомные параметры (контейнеры, кодеки, разрешения, аудио-кодеки)."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            containers = data.get("containers", [])
            codecs = data.get("codecs", [])
            resolutions = data.get("resolutions", [])
            audio_codecs = data.get("audio_codecs", [])
            if not isinstance(containers, list): containers = []
            if not isinstance(codecs, list): codecs = []
            if not isinstance(resolutions, list): resolutions = []
            if not isinstance(audio_codecs, list): audio_codecs = []
            self.customContainers = list(dict.fromkeys(self.customContainers + containers))
            self.customCodecs = list(dict.fromkeys(self.customCodecs + codecs))
            self.customResolutions = list(dict.fromkeys(self.customResolutions + resolutions))
            self.customAudioCodecs = list(dict.fromkeys(self.customAudioCodecs + audio_codecs))
            self._saveCustomOptions()
            return True
        except Exception:
            return False

    def saveCurrentCommand(self):
        """Сохраняет текущую команду из поля ввода под заданным именем (диалог)."""
        cmd = self.ui.commandDisplay.toPlainText().strip() if hasattr(self.ui, "commandDisplay") else ""
        if not cmd or cmd.lower() == "ffmpeg":
            QMessageBox.information(self, "Сохранение команды", "Введите команду в поле выше или сгенерируйте её, выбрав файл и пресет.")
            return
        name, ok = QInputDialog.getText(
            self,
            "Сохранить команду",
            "Введите имя для сохранённой команды:",
            text=""
        )
        if not ok or not name.strip():
            return
        name = name.strip()
        commands = self._loadSavedCommands()
        # Заменяем существующую запись с таким именем
        commands = [c for c in commands if c.get("name") != name]
        commands.append({"name": name, "command": cmd})
        self._saveSavedCommands(commands)
        QMessageBox.information(self, "Сохранено", f"Команда «{name}» сохранена.")

    def loadSavedCommand(self):
        """Загружает выбранную сохранённую команду и применяет её к выделенному файлу в очереди (пресет → custom)."""
        item = self.getSelectedQueueItem()
        if not item:
            QMessageBox.information(self, "Загрузить команду", "Сначала выберите файл в очереди.")
            return
        commands = self._loadSavedCommands()
        if not commands:
            QMessageBox.information(self, "Загрузить команду", "Нет сохранённых команд. Сохраните команду кнопкой «Сохранить команду».")
            return
        names = [c.get("name", "") for c in commands]
        name, ok = QInputDialog.getItem(
            self,
            "Загрузить команду",
            "Выберите сохранённую команду:",
            names,
            0,
            False
        )
        if not ok or not name:
            return
        entry = next((c for c in commands if c.get("name") == name), None)
        if not entry:
            return
        cmd = entry.get("command", "").strip()
        if not cmd:
            return
        item.preset_name = f"cmd:{name}"
        item.command = cmd
        item.command_manually_edited = True
        item.last_generated_command = getattr(item, "last_generated_command", "") or ""
        self.commandManuallyEdited = True
        if hasattr(self.ui, "commandDisplay"):
            self._applyPathsToSavedCommand(item, update_display=True)
            self.ui.commandDisplay.setReadOnly(False)
        self.updateQueueTable()
        QMessageBox.information(self, "Загружено", f"Команда «{name}» применена к выбранному файлу. При кодировании будут подставлены пути этого файла.")

    def deleteSavedCommand(self):
        """Удаляет выбранную сохранённую команду (диалог выбора)."""
        commands = self._loadSavedCommands()
        if not commands:
            QMessageBox.information(self, "Удалить команду", "Нет сохранённых команд.")
            return
        names = [c.get("name", "") for c in commands]
        name, ok = QInputDialog.getItem(
            self,
            "Удалить команду",
            "Выберите команду для удаления:",
            names,
            0,
            False
        )
        if not ok or not name:
            return
        commands = [c for c in commands if c.get("name") != name]
        self._saveSavedCommands(commands)
        QMessageBox.information(self, "Удалено", f"Команда «{name}» удалена из списка сохранённых.")

    def exportSelectedPreset(self):
        """Экспорт выбранного в таблице пресета в XML файл."""
        if not hasattr(self.ui, 'presetsTableWidget'):
            return
        table = self.ui.presetsTableWidget
        row = table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Пресеты", "Сначала выберите пресет в таблице.")
            return
        name_item = table.item(row, 0)
        if not name_item:
            return
        preset_name = name_item.text()
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Экспорт пресета",
            f"{preset_name}.xml",
            "XML файлы (*.xml)"
        )
        if not file_path:
            return
        if self.presetManager.exportPresetToFile(preset_name, file_path):
            QMessageBox.information(self, "Успех", f"Пресет \"{preset_name}\" экспортирован в:\n{file_path}")
        else:
            QMessageBox.critical(self, "Ошибка", "Не удалось экспортировать пресет.")
    
    def importPresetFromFile(self):
        """Импорт одного пресета из XML файла и обновление таблицы."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Импорт пресета",
            "",
            "XML файлы (*.xml)"
        )
        if not file_path:
            return
        ok = self.presetManager.importPresetFromFile(file_path)
        if ok:
            QMessageBox.information(self, "Успех", "Пресет успешно импортирован.")
            self.refreshPresetsTable()
        else:
            QMessageBox.critical(self, "Ошибка", "Не удалось импортировать пресет.")

    def openFileLocation(self, file_path):
        """Открывает папку с указанным файлом в проводнике."""
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "Ошибка", "Файл не найден.")
            return

        output_dir = os.path.dirname(file_path)
        if not os.path.exists(output_dir):
            QMessageBox.warning(self, "Ошибка", f"Папка не существует:\n{output_dir}")
            return

        # Открываем папку в зависимости от ОС
        if platform.system() == "Windows":
            os.startfile(output_dir)
        elif platform.system() == "Darwin":  # macOS
            os.system(f'open "{output_dir}"')
        else:  # Linux
            os.system(f'xdg-open "{output_dir}"')
