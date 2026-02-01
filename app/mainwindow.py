import os
import platform
import logging
from app.constants import (
    WINDOW_TITLE, WINDOW_WIDTH, WINDOW_HEIGHT,
    HEIGHT_PRESET_EDITOR_CONTAINER, HEIGHT_PRESET_EDITOR_LAYOUT, HEIGHT_BUTTON_PRESET,
    STYLE_RUN_BUTTON, STYLE_ABORT_BUTTON,
    VIDEO_UPDATE_INTERVAL_MS,
    ETA_DELAY_SECONDS, ETA_SMOOTHING_ALPHA,
    CONFIG_CUSTOM_OPTIONS, CONFIG_SAVED_COMMANDS, CONFIG_APP_CONFIG,
)
from PySide6.QtWidgets import QMainWindow, QMessageBox, QSpinBox, QComboBox, QTabWidget
from PySide6.QtCore import QProcess, QTimer, QEvent
from PySide6.QtGui import QGuiApplication, QCloseEvent
from ui.ui_mainwindow import Ui_MainWindow  # Сгенерированный из .ui интерфейс
from models.presetmanager import PresetManager
from mixins.config_warnings import ConfigWarningsMixin
from mixins.queue_ui import QueueUIMixin
from mixins.encoding_process import EncodingMixin
from mixins.preset_editor_ui import PresetEditorUIMixin
from mixins.video_preview import VideoPreviewMixin
from mixins.audio_pages import AudioPagesMixin

logger = logging.getLogger(__name__)


class MainWindow(QueueUIMixin, EncodingMixin, PresetEditorUIMixin, VideoPreviewMixin, AudioPagesMixin, ConfigWarningsMixin, QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self._runButtonStyleStart = STYLE_RUN_BUTTON
        self._runButtonStyleAbort = STYLE_ABORT_BUTTON
        if hasattr(self.ui, 'runButton'):
            self.ui.runButton.setStyleSheet(self._runButtonStyleStart)
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
            self.ui.PreviousFrame.setText("\u2190")
        if hasattr(self.ui, 'NextFrame'):
            self.ui.NextFrame.setText("\u2192")
        if hasattr(self.ui, 'presetEditorContainer'):
            self.ui.presetEditorContainer.setFixedHeight(HEIGHT_PRESET_EDITOR_CONTAINER)
        if hasattr(self.ui, 'verticalLayoutWidget_3'):
            self.ui.verticalLayoutWidget_3.setFixedHeight(HEIGHT_PRESET_EDITOR_LAYOUT)
        if hasattr(self.ui, 'createPresetButton'):
            self.ui.createPresetButton.setMaximumHeight(HEIGHT_BUTTON_PRESET)
            self.ui.createPresetButton.setStyleSheet("padding: 4px 10px;")
        if hasattr(self.ui, 'savePresetChangesButton'):
            self.ui.savePresetChangesButton.setMaximumHeight(HEIGHT_BUTTON_PRESET)
            self.ui.savePresetChangesButton.setStyleSheet("padding: 4px 10px;")
        for attr in ("savePresetWithCustomParamsButton", "savePresetCustomParamsButton", "savePresetWithExtraParamsButton"):
            btn = getattr(self.ui, attr, None)
            if btn is not None:
                btn.setMaximumHeight(HEIGHT_BUTTON_PRESET)
                btn.setStyleSheet("padding: 4px 10px;")

        self.ffmpegProcess = QProcess(self)
        # Корень проекта (для конфигов в корне)
        self._appDir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.presetManager = PresetManager(self._appDir)
        self.currentPresetName = None  # Текущий редактируемый пресет
        # Пользовательские опции (контейнеры, кодеки, разрешения, аудио-кодеки)
        self.customContainers = []
        self.customCodecs = []
        self.customResolutions = []
        self.customAudioCodecs = []
        self._customOptionsPath = os.path.join(self._appDir, CONFIG_CUSTOM_OPTIONS)
        self._savedCommandsPath = os.path.join(self._appDir, CONFIG_SAVED_COMMANDS)
        self._appConfigPath = os.path.join(self._appDir, CONFIG_APP_CONFIG)
        os.makedirs(os.path.dirname(self._customOptionsPath), exist_ok=True)  # presets/
        self._configWriteWarningsShown = set()
        self._ffmpegWarningShown = False
        self._ffprobeWarningShown = False
        self._loadCustomOptions()
        self.currentCodecCustom = ""  # Кастомный кодек для редактора пресетов
        self.currentContainerCustom = ""
        self.currentResolutionCustom = ""
        self.currentAudioCodecCustom = ""
        
        # Очередь файлов
        self.queue = []  # Список QueueItem
        self.currentQueueIndex = -1  # Индекс текущего обрабатываемого файла
        self.selectedQueueIndex = -1  # Индекс выделенного файла в таблице
        
        # Переменные для текущего файла
        self.inputFile = ""
        self.lastOutputFile = ""
        # Глобальные флаги
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
        self._etaDelaySeconds = ETA_DELAY_SECONDS
        self._etaSmoothingAlpha = ETA_SMOOTHING_ALPHA
        self._etaStartTs = None
        self._emaSpeed = None
        self._speedSampleCount = 0
        
        # Переменные для прогресса кодирования
        self.encodingProgress = 0
        self.currentFrame = 0
        self.videoDuration = 0
        self.encodingDuration = 0
        self.isPaused = False

        # Флаги управления остановкой очереди через кнопку "Пауза" / "Завершить кодирование"
        self._pauseStopRequested = False
        self._abortRequested = False  # нажата "Завершить кодирование"
        self._closingApp = False  # закрытие окна во время кодирования — не обрабатывать processFinished
        self.pausedQueueIndex = -1
        
        # Инициализация медиаплеера для предпросмотра
        self.initVideoPreview()
        
        # Инициализация очереди
        self.initQueue()

        # Инициализация редактора пресетов
        self.initPresetEditor()

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
        
        # Кнопки управления командой
        if hasattr(self.ui, 'commandDisplay'):
            self.ui.commandDisplay.textChanged.connect(self.onCommandManuallyEdited)
        if hasattr(self.ui, 'runButton'):
            self.ui.runButton.clicked.connect(self.onRunButtonClicked)
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

        # Кнопки редактора пресетов
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
        btn = getattr(self.ui, "savePresetWithCustomParamsButton", None)
        if btn is not None:
            btn.clicked.connect(self.savePresetWithCustomParams)
            btn.setToolTip("Сохраняет пресет вместе с дополнительными параметрами,\n"
                            "которые вы вручную дописали в команду FFmpeg.")

        # Лог выполнения команды ffmpeg
        if hasattr(self.ui, 'showFFmpegLogButton'):
            self.ui.showFFmpegLogButton.hide()

        # Подключение кнопок предпросмотра
        if hasattr(self.ui, 'videoPlayButton'):
            self.ui.videoPlayButton.clicked.connect(self.toggleVideoPlayback)
        if hasattr(self.ui, 'PreviousFrame'):
            self.ui.PreviousFrame.clicked.connect(self.stepVideoPreviousFrame)
        if hasattr(self.ui, 'NextFrame'):
            self.ui.NextFrame.clicked.connect(self.stepVideoNextFrame)
        if hasattr(self.ui, 'SetInPoint'):
            self.ui.SetInPoint.clicked.connect(self.setTrimStart)
        if hasattr(self.ui, 'SetOutPoint'):
            self.ui.SetOutPoint.clicked.connect(self.setTrimEnd)
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
        self.ffmpegProcess.errorOccurred.connect(self.onProcessError)
        
        # Таймер для обновления времени видео
        self.videoUpdateTimer = QTimer(self)
        self.videoUpdateTimer.timeout.connect(self.updateVideoTime)
        self.videoUpdateTimer.start(VIDEO_UPDATE_INTERVAL_MS)
        
        # Инициализация статуса
        self.updateStatus("Готов")

        # Лог выполнения всегда виден
        self.isLogVisible = True

        # Вкладки: очередь кодирования, «Видео в аудио», «Аудио конвертер»
        self._tabWidget = QTabWidget()
        self._tabWidget.addTab(self.ui.centralwidget, "Очередь кодирования")
        self._videoToAudioWidget = self._createVideoToAudioPage()
        self._tabWidget.addTab(self._videoToAudioWidget, "Видео в аудио")
        self._audioConverterWidget = self._createAudioConverterPage()
        self._tabWidget.addTab(self._audioConverterWidget, "Аудио конвертер")
        self.setCentralWidget(self._tabWidget)
        self._loadAppConfig()
        self._tabWidget.currentChanged.connect(self._saveAppConfig)

        self._warnIfConfigPathNotWritable()
        self._checkToolsAvailability()

    def closeEvent(self, event: QCloseEvent):
        """При закрытии во время кодирования — предупреждение и удаление битого файла при подтверждении."""
        self._saveAppConfig()
        v2a = getattr(self, "_v2aProcess", None)
        if v2a and v2a.state() != QProcess.NotRunning:
            reply = QMessageBox.question(
                self,
                "Завершить программу?",
                "Идёт конвертация «Видео в аудио». Вы уверены, что хотите завершить программу?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                v2a.kill()
                path = getattr(self, "_v2aLastOutputPath", "")
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                    except Exception:
                        pass
                event.accept()
            else:
                event.ignore()
            return
        a2a = getattr(self, "_a2aProcess", None)
        if a2a and a2a.state() != QProcess.NotRunning:
            reply = QMessageBox.question(
                self,
                "Завершить программу?",
                "Идёт конвертация «Аудио конвертер». Вы уверены, что хотите завершить программу?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                a2a.kill()
                path = getattr(self, "_a2aLastOutputPath", "")
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                    except Exception:
                        pass
                event.accept()
            else:
                event.ignore()
            return
        if self.currentQueueIndex >= 0 and self.currentQueueIndex < len(self.queue):
            reply = QMessageBox.question(
                self,
                "Завершить программу?",
                "У вас ещё перекодируются файлы. Вы уверены, что хотите завершить программу?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self._closingApp = True
                if self.ffmpegProcess.state() == QProcess.Running:
                    self.ffmpegProcess.kill()
                item = self.queue[self.currentQueueIndex]
                try:
                    if item.output_file and os.path.exists(item.output_file):
                        os.remove(item.output_file)
                except Exception:
                    pass
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

    def updateStatus(self, status_text):
        """Обновляет статус в статусбаре"""
        self.ui.statusbar.showMessage(status_text)

    def _openFolderOrSelectFile(self, path):
        """Открывает папку в проводнике; если path — существующий файл, на Windows/macOS выделяет его."""
        if not path:
            return
        out_dir = os.path.dirname(path) if os.path.isfile(path) else path
        if not os.path.isdir(out_dir):
            out_dir = os.path.dirname(path)
        if not out_dir or not os.path.exists(out_dir):
            return
        sys_name = platform.system()
        if sys_name == "Windows":
            if os.path.isfile(path) and os.path.exists(path):
                os.system(f'explorer /select,"{path}"')
            else:
                os.startfile(out_dir)
        elif sys_name == "Darwin":
            if os.path.isfile(path) and os.path.exists(path):
                os.system(f'open -R "{path}"')
            else:
                os.system(f'open "{out_dir}"')
        else:
            os.system(f'xdg-open "{out_dir}"')

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
        self._openFolderOrSelectFile(target_file)

    def copyCommand(self):
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(self.ui.commandDisplay.toPlainText())


    def openFileLocation(self, file_path):
        """Открывает папку с указанным файлом в проводнике (и выделяет файл, где поддерживается)."""
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "Ошибка", "Файл не найден.")
            return
        output_dir = os.path.dirname(file_path)
        if not os.path.exists(output_dir):
            QMessageBox.warning(self, "Ошибка", f"Папка не существует:\n{output_dir}")
            return
        self._openFolderOrSelectFile(file_path)
