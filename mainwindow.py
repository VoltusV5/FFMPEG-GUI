import sys
import os
import platform
import shlex
import re
from PySide6.QtWidgets import (QMainWindow, QFileDialog, QMessageBox, QInputDialog, 
                               QVBoxLayout, QTableWidgetItem, QProgressBar, QPushButton,
                               QHeaderView, QAbstractItemView, QButtonGroup, QWidget)
from PySide6.QtCore import QProcess, QUrl, Qt, QTimer, QMimeData, QRectF
from PySide6.QtGui import QGuiApplication, QDragEnterEvent, QDropEvent, QPainter, QColor, QBrush
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
        # Фон — тёмно-серая полоска под тему
        painter.fillRect(0, 0, w, h, QColor(0x40, 0x40, 0x40))
        # Добавленные области склейки — приглушённый зелёный
        for start, end in self.keep_segments:
            if end <= start:
                continue
            x1 = int(w * start / self.duration_sec)
            x2 = int(w * end / self.duration_sec)
            x1 = max(0, min(x1, w))
            x2 = max(0, min(x2, w))
            if x2 > x1:
                painter.fillRect(x1, 0, x2 - x1, h, QColor(56, 142, 60))  # #388e3c
        # Текущий промежуток in–out — акцентный синий
        if self.trim_start_sec is not None and self.trim_end_sec is not None and self.trim_end_sec > self.trim_start_sec:
            x1 = int(w * self.trim_start_sec / self.duration_sec)
            x2 = int(w * self.trim_end_sec / self.duration_sec)
            x1 = max(0, min(x1, w))
            x2 = max(0, min(x2, w))
            if x2 > x1:
                painter.fillRect(x1, 0, x2 - x1, h, QColor(0x4a, 0x9e, 0xff))
        painter.end()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle("OpenFF GUI - MVP")
        self.resize(900, 680)
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

        self.ffmpegProcess = QProcess(self)
        self.presetManager = PresetManager()
        self.currentPresetName = None  # Текущий редактируемый пресет
        self.currentCodecCustom = ""   # Кастомный кодек для редактора пресетов
        self.currentContainerCustom = ""  # Кастомный контейнер
        self.currentResolutionCustom = "" # Кастомное разрешение
        
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
        # По умолчанию скрываем интерфейс настройки пресетов,
        # он появится после выбора первого файла в очереди
        if hasattr(self.ui, 'presetEditorContainer'):
            self.ui.presetEditorContainer.hide()

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
        if hasattr(self.ui, 'openOutputFolderButton'):
            self.ui.openOutputFolderButton.clicked.connect(self.openOutputFolder)

        # Кнопки редактора пресетов (новый UI)
        if hasattr(self.ui, 'presetExportButton'):
            self.ui.presetExportButton.clicked.connect(self.exportSelectedPreset)
        if hasattr(self.ui, 'presetImportButton'):
            self.ui.presetImportButton.clicked.connect(self.importPresetFromFile)
        if hasattr(self.ui, 'createPresetButton'):
            self.ui.createPresetButton.clicked.connect(self.createPreset)
        if hasattr(self.ui, 'savePresetChangesButton'):
            self.ui.savePresetChangesButton.clicked.connect(self.saveCurrentPreset)

        # Кнопка показа/скрытия лога
        if hasattr(self.ui, 'showFFmpegLogButton'):
            self.ui.showFFmpegLogButton.clicked.connect(self.toggleLogVisibility)
        
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

        # Состояние показа лога
        self.isLogVisible = False
        self.normalSize = (900, 680)  # Обычный размер
        self.expandedSize = (900, 950)  # Размер с видимым логом

        # Начально скрываем лог
        self.hideLog()
    
    def initQueue(self):
        """Инициализирует таблицу очереди"""
        if not hasattr(self.ui, 'queueTableWidget'):
            return
        
        # Настраиваем таблицу
        table = self.ui.queueTableWidget
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels([
            "Входной файл", "Выходной файл", "Пресет", "Статус", "Прогресс", "Открыть папку"
        ])
        
        # Разрешаем множественное выделение строк (для массового применения пресетов)
        table.setSelectionMode(QAbstractItemView.ExtendedSelection)

        # Настройка столбцов
        header = table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Fixed)  # Входной файл - фиксированная ширина
        table.setColumnWidth(0, 250)  # Уменьшено для оптимизации места
        header.setSectionResizeMode(1, QHeaderView.Fixed)  # Выходной файл
        table.setColumnWidth(1, 200)  # Оптимизированная ширина
        header.setSectionResizeMode(2, QHeaderView.Fixed)  # Пресет
        table.setColumnWidth(2, 80)
        header.setSectionResizeMode(3, QHeaderView.Fixed)  # Статус
        table.setColumnWidth(3, 100)
        header.setSectionResizeMode(4, QHeaderView.Fixed)  # Прогресс
        table.setColumnWidth(4, 80)
        header.setSectionResizeMode(5, QHeaderView.Fixed)  # Открыть папку
        table.setColumnWidth(5, 100)  # На 10 пикселей больше
        
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

    # ===== Инициализация и логика редактора пресетов (новый UI) =====

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
        # Фиксированные ширины колонок:
        # 0: Название  - в 2 раза меньше прежнего (~75)
        # 1: Описание  - ~0.75 от прежней (~165)
        # 2: Удалить   - ~0.75 от прежней (~70)
        # 3: Применить - ~0.5 от прежней (~90)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Fixed)
        table.setColumnWidth(0, 75)
        table.setColumnWidth(1, 205)  # Описание: +40 пикселей
        table.setColumnWidth(2, 70)
        table.setColumnWidth(3, 90)

        # Группы кнопок для кодека
        self.codecButtonGroup = QButtonGroup(self)
        self.codecButtonGroup.setExclusive(True)
        for attr in ['codecCurrentButton', 'codecLibx264Button', 'codecLibx265Button', 'codecCustomButton']:
            if hasattr(self.ui, attr):
                btn = getattr(self.ui, attr)
                btn.setCheckable(True)
                self.codecButtonGroup.addButton(btn)
        if hasattr(self, 'codecButtonGroup'):
            self.codecButtonGroup.buttonClicked.connect(self.onCodecButtonClicked)

        # Группа кнопок для контейнера
        self.containerButtonGroup = QButtonGroup(self)
        self.containerButtonGroup.setExclusive(True)
        for attr in ['containerCurrentButton', 'containerMp4Button', 'containerMkvButton', 'containerCustomButton']:
            if hasattr(self.ui, attr):
                btn = getattr(self.ui, attr)
                btn.setCheckable(True)
                self.containerButtonGroup.addButton(btn)
        if hasattr(self, 'containerButtonGroup'):
            self.containerButtonGroup.buttonClicked.connect(self.onContainerButtonClicked)

        # Группа кнопок для разрешения
        self.resolutionButtonGroup = QButtonGroup(self)
        self.resolutionButtonGroup.setExclusive(True)
        for attr in ['resolutionCurrentButton', 'resolution480pButton',
                     'resolution720pButton', 'resolution1080pButton',
                     'resolutionCustomButton']:
            if hasattr(self.ui, attr):
                btn = getattr(self.ui, attr)
                btn.setCheckable(True)
                self.resolutionButtonGroup.addButton(btn)
        if hasattr(self, 'resolutionButtonGroup'):
            self.resolutionButtonGroup.buttonClicked.connect(self.onResolutionButtonClicked)

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
                self.videoWidget = QVideoWidget(self.ui.videoPreviewWidget)
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

            # Столбец 5: Кнопка "Открыть папку" (только для завершенных файлов)
            if item.status == QueueItem.STATUS_SUCCESS and item.output_file:
                open_btn = QPushButton("Открыть папку")
                open_btn.clicked.connect(lambda _, path=item.output_file: self.openFileLocation(path))
                table.setCellWidget(row, 5, open_btn)
            else:
                # Для незавершенных файлов - пустая ячейка
                empty_item = QTableWidgetItem("")
                empty_item.setFlags(empty_item.flags() & ~Qt.ItemIsEditable)
                table.setItem(row, 5, empty_item)

        # Восстанавливаем сигналы
        table.blockSignals(False)
    
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
            self.commandManuallyEdited = True
            self.lastGeneratedCommand = getattr(item, "last_generated_command", "")
            self.ui.commandDisplay.setPlainText(item.command)
        else:
            self.commandManuallyEdited = False
            self.updateCommandFromGUI()

        # Обновляем редактор пресетов под текущий файл
        self.syncPresetEditorWithQueueItem(item)

        # При выборе файла показываем редактор пресетов
        if hasattr(self.ui, 'presetEditorContainer'):
            self.ui.presetEditorContainer.show()
        # Расширяем окно для показа редактора (независимо от лога)
        self.resize(1400, 680)

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
            name_item = QTableWidgetItem(p["name"])
            desc_item = QTableWidgetItem(p.get("description", ""))
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            desc_item.setFlags(desc_item.flags() & ~Qt.ItemIsEditable)
            # При наведении показываем полное название и полное описание
            name_item.setToolTip(p["name"])
            desc_item.setToolTip(p.get("description", ""))
            table.setItem(row, 0, name_item)
            table.setItem(row, 1, desc_item)

            # Кнопка "Удалить пресет"
            delete_btn = QPushButton("Удалить")
            delete_btn.clicked.connect(lambda _, n=p["name"]: self.onDeletePresetClicked(n))
            table.setCellWidget(row, 2, delete_btn)

            # Кнопка "Применить к выбранному файлу"
            apply_btn = QPushButton("Применить")
            apply_btn.clicked.connect(lambda _, n=p["name"]: self.onApplyPresetClicked(n))
            table.setCellWidget(row, 3, apply_btn)

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
        preset_name = name_item.text()
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

    def _getCodecFromButtons(self):
        """Возвращает строковое значение codec на основе нажатой кнопки."""
        if hasattr(self.ui, 'codecCurrentButton') and self.ui.codecCurrentButton.isChecked():
            return "current"
        if hasattr(self.ui, 'codecLibx264Button') and self.ui.codecLibx264Button.isChecked():
            return "libx264"
        if hasattr(self.ui, 'codecLibx265Button') and self.ui.codecLibx265Button.isChecked():
            return "libx265"
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
        if hasattr(self.ui, 'resolutionCustomButton') and self.ui.resolutionCustomButton.isChecked():
            return self.currentResolutionCustom or "current"
        return "current"

    def syncPresetEditorWithPresetData(self, preset):
        """Устанавливает состоние кнопок редактора по данным пресета."""
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
        else:
            # Кастомный кодек
            self.currentCodecCustom = codec
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
        else:
            self.currentContainerCustom = container
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
        else:
            self.currentResolutionCustom = resolution
            if hasattr(self.ui, 'resolutionCustomButton'):
                self.ui.resolutionCustomButton.setChecked(True)

    def syncPresetEditorWithQueueItem(self, item: QueueItem):
        """При выборе файла в очереди подтягиваем в редактор его текущие параметры."""
        preset_data = {
            "codec": item.codec,
            "container": item.container,
            "resolution": item.resolution,
        }
        self.currentPresetName = item.preset_name
        self.syncPresetEditorWithPresetData(preset_data)

    # --- Обработчики кликов по кнопкам редактора пресетов ---

    def onCodecButtonClicked(self, button):
        """Обработчик выбора кодека в редакторе пресетов."""
        if hasattr(self.ui, 'codecCustomButton') and button is self.ui.codecCustomButton:
            text, ok = QInputDialog.getText(
                self,
                "Пользовательский кодек",
                "Введите имя видеокодека (например, libx264):",
                text=self.currentCodecCustom or "libx264"
            )
            if ok and text.strip():
                self.currentCodecCustom = text.strip()
        # Обновляем команду после выбора
        self.updateCommandFromPresetEditor()

    def onContainerButtonClicked(self, button):
        """Обработчик выбора контейнера в редакторе пресетов."""
        if hasattr(self.ui, 'containerCustomButton') and button is self.ui.containerCustomButton:
            text, ok = QInputDialog.getText(
                self,
                "Пользовательский контейнер",
                "Введите расширение контейнера (например, mp4):",
                text=self.currentContainerCustom or "mp4"
            )
            if ok and text.strip():
                self.currentContainerCustom = text.strip().lstrip(".")
        # Обновляем команду после выбора
        self.updateCommandFromPresetEditor()

    def onResolutionButtonClicked(self, button):
        """Обработчик выбора разрешения в редакторе пресетов."""
        if hasattr(self.ui, 'resolutionCustomButton') and button is self.ui.resolutionCustomButton:
            text, ok = QInputDialog.getText(
                self,
                "Пользовательское разрешение",
                "Введите разрешение в формате width:height (например, 1920:1080):",
                text=self.currentResolutionCustom or "1920:1080"
            )
            if ok and text.strip():
                self.currentResolutionCustom = text.strip()
        # Обновляем команду после выбора
        self.updateCommandFromPresetEditor()

    def updateCommandFromPresetEditor(self):
        """Обновляет команду FFmpeg на основе текущих настроек редактора пресетов."""
        table = self.ui.queueTableWidget if hasattr(self.ui, 'queueTableWidget') else None
        if not table:
            return

        selected_rows = table.selectionModel().selectedRows()
        indices = sorted([r.row() for r in selected_rows])
        if not indices:
            # Нет выделенных файлов — нечего обновлять
            return

        # Получаем текущие значения из кнопок редактора
        codec = self._getCodecFromButtons()
        container = self._getContainerFromButtons()
        resolution = self._getResolutionFromButtons()

        # Обновляем параметры во всех выделенных QueueItem
        default_like = ("default", "current", "")
        for idx in indices:
            if 0 <= idx < len(self.queue):
                item = self.queue[idx]

                # Обновляем параметры в QueueItem
                item.codec = codec
                item.container = container
                item.resolution = resolution

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

                # Маркируем пресет для файла
                if (codec in default_like and
                    container in default_like and
                    resolution in default_like):
                    item.preset_name = "default"
                else:
                    item.preset_name = "custom"

        # При массовом изменении не трогаем текст команды (для нескольких файлов она не отображается),
        # достаточно того, что параметры в QueueItem изменены.
        self.commandManuallyEdited = False
        self.updateQueueTable()

    # ===== Методы для управления видимостью лога =====

    def toggleLogVisibility(self):
        """Переключает видимость лога FFmpeg и размер окна."""
        if self.isLogVisible:
            self.hideLog()
        else:
            self.showLog()

    def showLog(self):
        """Показывает лог и расширяет окно."""
        if hasattr(self.ui, 'logDisplay'):
            self.ui.logDisplay.show()
        if hasattr(self.ui, 'openOutputFolderButton'):
            self.ui.openOutputFolderButton.show()
        # Всегда расширяем окно при показе лога
        self.resize(self.expandedSize[0], self.expandedSize[1])
        self.isLogVisible = True
        if hasattr(self.ui, 'showFFmpegLogButton'):
            self.ui.showFFmpegLogButton.setText("Скрыть лог FFmpeg")

    def hideLog(self):
        """Скрывает лог и сжимает окно."""
        if hasattr(self.ui, 'logDisplay'):
            self.ui.logDisplay.hide()
        if hasattr(self.ui, 'openOutputFolderButton'):
            self.ui.openOutputFolderButton.hide()
        # Всегда сжимаем окно при скрытии лога
        self.resize(self.normalSize[0], self.normalSize[1])
        self.isLogVisible = False
        if hasattr(self.ui, 'showFFmpegLogButton'):
            self.ui.showFFmpegLogButton.setText("Показать лог FFmpeg")
    
    def getSelectedQueueItem(self):
        """Возвращает выделенный элемент очереди или None"""
        if self.selectedQueueIndex >= 0 and self.selectedQueueIndex < len(self.queue):
            return self.queue[self.selectedQueueIndex]
        return None
    
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

        # Параметры разрешения:
        # - "current"/"default" => не добавляем фильтр scale
        # - "480p"/"720p"/"1080p" => фиксированные значения
        # - любое другое значение с ":" или "x" => используем как custom разрешение
        res = item.resolution or "current"
        scale = ""
        if res == "480p":
            scale = "scale=854:480"
        elif res == "720p":
            scale = "scale=1280:720"
        elif res == "1080p":
            scale = "scale=1920:1080"
        else:
            custom = item.custom_resolution or res
            if isinstance(custom, str) and (":" in custom or "x" in custom):
                custom = custom.replace("x", ":")
                scale = "scale=" + custom

        vf_args = []
        if scale:
            vf_args = ["-vf", scale]

        segments = self._getTrimSegments(item)
        cmd_parts = ["ffmpeg"]
        if len(segments) == 1:
            start_sec, end_sec = segments[0]
            cmd_parts += ["-ss", str(start_sec), "-i", self._quotePath(input_file_normalized), "-to", str(end_sec)]
            cmd_parts += vf_args
            cmd_parts += codec_args
        elif len(segments) > 1:
            filter_complex, _ = self._buildTrimConcatFilter(segments, scale)
            codec_display = codec if codec not in ("default", "current", "") else "libx264"
            cmd_parts += ["-i", self._quotePath(input_file_normalized), "-filter_complex", f'"{filter_complex}"', "-map", "[v]", "-map", "[outa]", "-c:v", codec_display, "-c:a", "aac"]
        else:
            cmd_parts += ["-i", self._quotePath(input_file_normalized)]
            cmd_parts += vf_args
            cmd_parts += codec_args
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

        # Параметры разрешения
        res = queue_item.resolution or "current"
        scale = ""
        if res == "480p":
            scale = "scale=854:480"
        elif res == "720p":
            scale = "scale=1280:720"
        elif res == "1080p":
            scale = "scale=1920:1080"
        else:
            custom = queue_item.custom_resolution or res
            if isinstance(custom, str) and (":" in custom or "x" in custom):
                custom = custom.replace("x", ":")
                scale = "scale=" + custom

        vf_args = []
        if scale:
            vf_args = ["-vf", scale]

        # Сегменты обрезки/склейки
        segments = self._getTrimSegments(queue_item)
        # Для обрезки увеличиваем analyzeduration/probesize, чтобы FFmpeg корректно определил кодеки
        probe_args = ["-analyzeduration", "10000000", "-probesize", "10000000"] if segments else []
        if len(segments) == 1:
            start_sec, end_sec = segments[0]
            args = probe_args + ["-ss", str(start_sec), "-i", input_file_normalized, "-to", str(end_sec)]
            args += vf_args
            args += codec_args
            args.append(final_output)
        elif len(segments) > 1:
            filter_complex, map_v = self._buildTrimConcatFilter(segments, scale)
            codec_val = (queue_item.codec or "libx264") if (queue_item.codec and queue_item.codec not in ("default", "current", "")) else "libx264"
            args = probe_args + ["-i", input_file_normalized, "-filter_complex", filter_complex, "-map", map_v, "-map", "[outa]", "-c:v", codec_val, "-c:a", "aac", final_output]
        else:
            args = ["-i", input_file_normalized]
            args += vf_args
            args += codec_args
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
            self.ui.pauseResumeButton.setText("⏸ Пауза")
        
        # Сбрасываем прогресс
        self.encodingDuration = 0
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

    def updateTotalQueueProgress(self):
        """Обновляет общий прогресс-бар для всей очереди файлов."""
        if not self.queue or not hasattr(self.ui, 'totalQueueProgressBar'):
            return

        total_files = len(self.queue)
        completed_files = sum(1 for item in self.queue if item.status == QueueItem.STATUS_SUCCESS)

        # Если есть обрабатываемый файл, добавляем его прогресс
        current_progress = 0
        if self.currentQueueIndex >= 0 and self.currentQueueIndex < len(self.queue):
            current_item = self.queue[self.currentQueueIndex]
            if current_item.status == QueueItem.STATUS_PROCESSING:
                current_progress = current_item.progress

        # Общий прогресс = завершенные файлы + текущий прогресс текущего файла
        total_progress = completed_files * 100 + current_progress

        # Максимум = общее количество файлов * 100
        max_progress = total_files * 100

        if max_progress > 0:
            percentage = int(total_progress / max_progress * 100)
            self.ui.totalQueueProgressBar.setValue(percentage)
        else:
            self.ui.totalQueueProgressBar.setValue(0)
    
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
                self.ui.videoPlayButton.setText("▶ Play")
        else:
            self.mediaPlayer.play()
            if hasattr(self.ui, 'videoPlayButton'):
                self.ui.videoPlayButton.setText("⏸ Pause")
    
    def stopVideo(self):
        """Останавливает воспроизведение видео"""
        if not self.mediaPlayer:
            return
        self.mediaPlayer.stop()
        if hasattr(self.ui, 'videoPlayButton'):
            self.ui.videoPlayButton.setText("▶ Play")

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
                self.ui.videoPlayButton.setText("⏸ Pause")
            else:
                self.ui.videoPlayButton.setText("▶ Play")
    
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
            self.ui.pauseResumeButton.setText("▶ Возобновить")
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
            self.ui.pauseResumeButton.setText("⏸ Пауза")

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

            # Используем ffprobe для получения длительности
            cmd = [ffprobe_executable, '-v', 'error', '-show_entries', 'format=duration', 
                   '-of', 'default=noprint_wrappers=1:nokey=1', item.file_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                duration_str = result.stdout.strip()
                if duration_str:
                    item.video_duration = float(duration_str)
                    self.videoDuration = item.video_duration
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
            self.ui.logDisplay.append(f"<br><b><font color='green'>✓ Файл обработан успешно: {os.path.basename(item.file_path)}</font></b>")
        else:
            item.status = QueueItem.STATUS_ERROR
            item.error_message = f"Код завершения: {exitCode}"
            self.ui.logDisplay.append(f"<br><b><font color='red'>✗ Ошибка обработки файла: {os.path.basename(item.file_path)} (код: {exitCode})</font></b>")
        
        # Обновляем таблицу
        self.updateQueueTable()
        self.updateTotalQueueProgress()
        
        # Обновляем прогресс-бар
        if hasattr(self.ui, 'encodingProgressBar'):
            self.ui.encodingProgressBar.setValue(100 if exitCode == 0 else 0)
        
        # Отключаем кнопку паузы
        if hasattr(self.ui, 'pauseResumeButton'):
            self.ui.pauseResumeButton.setEnabled(False)
            self.ui.pauseResumeButton.setText("⏸ Пауза")
        
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
        if not self.lastOutputFile:
            QMessageBox.warning(self, "Ошибка", "Выходной файл не найден")
            return
        
        output_dir = os.path.dirname(self.lastOutputFile)
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


    # ===== Новые методы создания/сохранения пресетов через редактор =====

    def createPreset(self):
        """Создаёт новый пресет на основе текущих настроек редактора пресетов."""
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

        self.presetManager.savePreset(name, codec, resolution, container, desc.strip())
        self.currentPresetName = name
        self.refreshPresetsTable()

    def saveCurrentPreset(self):
        """Сохраняет изменения в текущий выбранный пресет, либо создаёт новый, если пресет ещё не выбран."""
        codec = self._getCodecFromButtons()
        container = self._getContainerFromButtons()
        resolution = self._getResolutionFromButtons()

        name = self.currentPresetName
        if not name or name == "custom":
            # Для custom или отсутствующего пресета запрашиваем имя
            name, ok = QInputDialog.getText(self, "Сохранить пресет", "Имя пресета:")
            if not ok or not name.strip():
                return
            name = name.strip()

        desc = ""
        existing = self.presetManager.loadPreset(name)
        if existing and existing.get("description"):
            desc = existing["description"]

        self.presetManager.savePreset(name, codec, resolution, container, desc)
        self.currentPresetName = name
        self.refreshPresetsTable()

    def copyCommand(self):
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(self.ui.commandDisplay.toPlainText())
        QMessageBox.information(self, "Скопировано", "Команда скопирована в буфер обмена!")
    
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
