import sys
import os
import platform
import shlex
import re
from PySide6.QtWidgets import (QMainWindow, QFileDialog, QMessageBox, QInputDialog, 
                               QVBoxLayout, QTableWidgetItem, QProgressBar, QPushButton,
                               QHeaderView, QAbstractItemView, QButtonGroup)
from PySide6.QtCore import QProcess, QUrl, Qt, QTimer, QMimeData
from PySide6.QtGui import QGuiApplication, QDragEnterEvent, QDropEvent
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from ui_mainwindow import Ui_MainWindow  # Сгенерированный из .ui интерфейс
from presetmanager import PresetManager
from queueitem import QueueItem

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle("OpenFF GUI - MVP")
        self.resize(900, 750)

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
        
        # Инициализация медиаплеера для предпросмотра
        self.initVideoPreview()
        
        # Инициализация очереди
        self.initQueue()

        # Инициализация редактора пресетов (новый UI)
        self.initPresetEditor()

        # Подключение сигналов
        # Кнопки очереди
        if hasattr(self.ui, 'addFilesButton'):
            self.ui.addFilesButton.clicked.connect(self.addFilesToQueue)
        if hasattr(self.ui, 'removeFromQueueButton'):
            self.ui.removeFromQueueButton.clicked.connect(self.removeSelectedFromQueue)
        
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
        
        # Подключение кнопок предпросмотра (если они существуют)
        if hasattr(self.ui, 'videoPlayButton'):
            self.ui.videoPlayButton.clicked.connect(self.toggleVideoPlayback)
        if hasattr(self.ui, 'videoStopButton'):
            self.ui.videoStopButton.clicked.connect(self.stopVideo)
        if hasattr(self.ui, 'videoMuteButton'):
            self.ui.videoMuteButton.clicked.connect(self.toggleVideoMute)
        if hasattr(self.ui, 'videoTimelineSlider'):
            self.ui.videoTimelineSlider.sliderMoved.connect(self.seekVideo)
            self.ui.videoTimelineSlider.sliderPressed.connect(self.pauseVideoForSeek)
            self.ui.videoTimelineSlider.sliderReleased.connect(self.resumeVideoAfterSeek)
        
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
    
    def initQueue(self):
        """Инициализирует таблицу очереди"""
        if not hasattr(self.ui, 'queueTableWidget'):
            return
        
        # Настраиваем таблицу
        table = self.ui.queueTableWidget
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Входной файл", "Пресет", "Статус", "Прогресс"])
        
        # Настройка столбцов
        header = table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # Файл - растягивается
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Пресет
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Статус
        header.setSectionResizeMode(3, QHeaderView.Fixed)  # Прогресс
        table.setColumnWidth(3, 150)
        
        # Настройка drag-and-drop
        table.setAcceptDrops(True)
        table.setDragDropMode(QAbstractItemView.DropOnly)
        table.setDefaultDropAction(Qt.CopyAction)
        
        # Подключаем сигналы
        table.itemSelectionChanged.connect(self.onQueueItemSelected)
        table.cellDoubleClicked.connect(self.onQueueCellDoubleClicked)
        
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
            "Название пресета", "Описание пресета",
            "Удалить пресет", "Применить к выбранному файлу"
        ])
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)

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
        except Exception as e:
            print(f"Ошибка инициализации медиаплеера: {e}")
            self.mediaPlayer = None
    
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
        
        # Обновляем таблицу
        self.updateQueueTable()
        
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
                self.selectedQueueIndex = new_index
                table.clearSelection()
                table.selectRow(new_index)
            else:
                # Очередь пуста — сбрасываем состояние
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
        table.setRowCount(len(self.queue))
        
        for row, item in enumerate(self.queue):
            # Столбец 0: Входной файл
            file_item = QTableWidgetItem(item.file_path)
            file_item.setFlags(file_item.flags() & ~Qt.ItemIsEditable)
            table.setItem(row, 0, file_item)
            
            # Столбец 1: Пресет
            preset_text = item.preset_name if item.preset_name else "Не выбран"
            preset_item = QTableWidgetItem(preset_text)
            preset_item.setFlags(preset_item.flags() & ~Qt.ItemIsEditable)
            table.setItem(row, 1, preset_item)
            
            # Столбец 2: Статус
            status_item = QTableWidgetItem(item.getStatusText())
            status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
            table.setItem(row, 2, status_item)
            
            # Столбец 3: Прогресс
            progress_text = f"{item.progress}%"
            progress_item = QTableWidgetItem(progress_text)
            progress_item.setFlags(progress_item.flags() & ~Qt.ItemIsEditable)
            table.setItem(row, 3, progress_item)
    
    def selectQueueItem(self, index):
        """Выделяет элемент очереди по индексу"""
        if not hasattr(self.ui, 'queueTableWidget') or index < 0 or index >= len(self.queue):
            return
        
        table = self.ui.queueTableWidget
        table.selectRow(index)
        self.selectedQueueIndex = index
        
        # Загружаем файл в предпросмотр и обновляем команду
        item = self.queue[index]
        self.inputFile = item.file_path
        
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
    
    def onQueueItemSelected(self):
        """Обработчик выделения элемента в таблице"""
        table = self.ui.queueTableWidget
        selected_rows = table.selectionModel().selectedRows()
        
        if selected_rows:
            row = selected_rows[0].row()
            if 0 <= row < len(self.queue) and row != self.selectedQueueIndex:
                # Вызываем selectQueueItem только если реально изменился индекс,
                # чтобы не зациклить выбор строки через сигнал itemSelectionChanged.
                self.selectQueueItem(row)
    
    def onQueueCellDoubleClicked(self, row, column):
        """Обработчик двойного клика по ячейке таблицы"""
        if column == 1:  # Клик по столбцу "Пресет"
            self.selectPresetForQueueItem(row)
    
    def selectPresetForQueueItem(self, row):
        """Открывает диалог выбора пресета для элемента очереди"""
        if row < 0 or row >= len(self.queue):
            return
        
        item = self.queue[row]
        names = self.presetManager.presetNames()
        
        if not names:
            QMessageBox.information(self, "Пресеты", "Нет сохранённых пресетов")
            return
        
        selected, ok = QInputDialog.getItem(
            self, 
            "Выбрать пресет", 
            "Выберите пресет для файла:", 
            names, 
            0, 
            False
        )
        
        if ok and selected:
            preset = self.presetManager.loadPreset(selected)
            if preset:
                item.preset_name = selected
                item.setPreset(preset)
                
                # Обновляем таблицу
                self.updateQueueTable()
                
                # Если это выделенный файл, обновляем команду
                if row == self.selectedQueueIndex:
                    self.commandManuallyEdited = False
                    self.updateCommandFromGUI()
                else:
                    # Если не выделенный, просто обновляем команду в памяти
                    # (она будет сгенерирована при выделении)
                    pass

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
                self.ui.commandDisplay.setPlainText(new_cmd)
            # Сохраняем автосгенерированную команду в QueueItem
            item.last_generated_command = new_cmd
            item.command = new_cmd
            item.command_manually_edited = False
        else:
            # Если команда уже была отредактирована вручную, просто обновим
            # сохранённое значение в QueueItem (на случай, если пользователь поправил что‑то ещё)
            item.command = self.ui.commandDisplay.toPlainText()
        
        # Обновляем таблицу (на случай если изменился пресет)
        self.updateQueueTable()
    
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
        """Оборачивает путь в кавычки, если он содержит пробелы или специальные символы"""
        if ' ' in path or '[' in path or ']' in path or '(' in path or ')' in path:
            return f'"{path}"'
        return path

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
        """Применяет выбранный пресет к текущему файлу в очереди и обновляет редактор."""
        item = self.getSelectedQueueItem()
        if not item:
            QMessageBox.information(self, "Очередь", "Сначала выберите файл в очереди.")
            return

        preset = self.presetManager.loadPreset(name)
        if not preset:
            QMessageBox.warning(self, "Пресеты", "Не удалось загрузить пресет.")
            return

        item.preset_name = name
        item.setPreset(preset)
        self.currentPresetName = name

        # Синхронизируем кнопки редактора пресетов
        self.syncPresetEditorWithPresetData(preset)

        # Обновляем команду
        self.commandManuallyEdited = False
        self.updateCommandFromGUI()
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
        item = self.getSelectedQueueItem()
        if not item:
            return

        # Получаем текущие значения из кнопок редактора
        codec = self._getCodecFromButtons()
        container = self._getContainerFromButtons()
        resolution = self._getResolutionFromButtons()

        # Обновляем параметры в QueueItem
        item.codec = codec
        item.container = container
        item.resolution = resolution

        # Устанавливаем custom resolution если выбрано
        if resolution == "custom":
            item.custom_resolution = self.currentResolutionCustom
        else:
            item.custom_resolution = ""

        # Если пользователь изменил параметры через редактор, и это не default,
        # то считаем что для файла теперь custom настройки
        if codec not in ("default", "current") or container not in ("default", "current") or resolution not in ("default", "current"):
            item.preset_name = "custom"
        else:
            item.preset_name = "default"

        # Перегенерируем команду
        self.commandManuallyEdited = False
        self.updateCommandFromGUI()
        self.updateQueueTable()
    
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
        input_path = os.path.dirname(input_file_normalized)
        input_base = os.path.splitext(os.path.basename(input_file_normalized))[0]

        # Определяем контейнер/расширение:
        # - "default" или "current" => использовать расширение исходного файла
        # - иное значение => использовать его как расширение (например, "mp4", "mkv")
        container = item.container or "current"
        if container in ("default", "current", "", None):
            out_ext = os.path.splitext(input_file_normalized)[1].lstrip(".")
        else:
            out_ext = container

        base_output = os.path.join(input_path, input_base + "_converted")
        output_file = base_output + "." + out_ext

        # Уникальное имя выходного файла
        counter = 1
        final_output = output_file
        while os.path.exists(final_output):
            final_output = base_output + "_" + str(counter) + "." + out_ext
            counter += 1
        
        # Нормализуем выходной путь
        final_output = os.path.normpath(final_output)
        
        # Сохраняем путь к выходному файлу
        item.output_file = final_output
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

        # Формируем команду для отображения (с кавычками вокруг путей)
        cmd_parts = ["ffmpeg", "-i", self._quotePath(input_file_normalized)]
        cmd_parts += vf_args
        cmd_parts += codec_args
        cmd_parts.append(self._quotePath(final_output))

        return " ".join(cmd_parts)
    
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
        input_path = os.path.dirname(input_file_normalized)
        input_base = os.path.splitext(os.path.basename(input_file_normalized))[0]

        # Контейнер/расширение
        container = queue_item.container or "current"
        if container in ("default", "current", "", None):
            out_ext = os.path.splitext(input_file_normalized)[1].lstrip(".")
        else:
            out_ext = container

        base_output = os.path.join(input_path, input_base + "_converted")
        output_file = base_output + "." + out_ext

        # Уникальное имя выходного файла
        counter = 1
        final_output = output_file
        while os.path.exists(final_output):
            final_output = base_output + "_" + str(counter) + "." + out_ext
            counter += 1
        
        # Нормализуем выходной путь
        final_output = os.path.normpath(final_output)
        
        # Сохраняем путь к выходному файлу в элементе очереди
        queue_item.output_file = final_output
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

        # Формируем список аргументов (без кавычек, QProcess сам обработает пробелы)
        args = ["-i", input_file_normalized]
        args += vf_args
        args += codec_args
        args.append(final_output)

        return args

    def startQueueProcessing(self):
        """Начинает обработку очереди файлов"""
        if not self.queue:
            QMessageBox.information(self, "Очередь", "Очередь пуста. Добавьте файлы для обработки.")
            return
        
        if self.ffmpegProcess.state() != QProcess.NotRunning:
            QMessageBox.information(self, "Ожидание", "Дождитесь завершения текущего кодирования")
            return
        
        # Начинаем обработку с первого файла
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
        if not self.ffmpegProcess or self.ffmpegProcess.state() == QProcess.NotRunning:
            return
        
        if self.isPaused:
            # Возобновляем
            self.resumeEncoding()
        else:
            # Ставим на паузу
            self.pauseEncoding()
    
    def pauseEncoding(self):
        """Приостанавливает кодирование"""
        if self.ffmpegProcess.state() != QProcess.Running:
            return
        
        if self.currentQueueIndex < 0 or self.currentQueueIndex >= len(self.queue):
            return
        
        item = self.queue[self.currentQueueIndex]
        self.isPaused = True
        item.status = QueueItem.STATUS_PAUSED
        
        # Сохраняем текущую команду и аргументы для возобновления
        self.pausedCommand = self.ui.commandDisplay.toPlainText()
        self.pausedArgs = self._getFFmpegArgs(item)
        self.pausedQueueIndex = self.currentQueueIndex
        
        # Пытаемся приостановить процесс через сигналы
        try:
            if platform.system() == "Windows":
                # На Windows останавливаем процесс
                # При возобновлении начнём с того же файла
                self.ffmpegProcess.kill()
                QMessageBox.information(self, "Информация", 
                    f"Кодирование приостановлено.\n"
                    f"При возобновлении обработка начнётся с файла:\n{os.path.basename(item.file_path)}")
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
        
        if hasattr(self.ui, 'pauseResumeButton'):
            self.ui.pauseResumeButton.setText("▶ Возобновить")
        self.updateStatus("Приостановлено...")
    
    def resumeEncoding(self):
        """Возобновляет кодирование"""
        if not self.isPaused:
            return
        
        # На Windows продолжаем с того же файла, на котором была пауза
        if platform.system() == "Windows":
            if hasattr(self, 'pausedQueueIndex') and self.pausedQueueIndex >= 0:
                # Возобновляем с файла, на котором была пауза
                self.currentQueueIndex = self.pausedQueueIndex
                item = self.queue[self.currentQueueIndex]
                item.status = QueueItem.STATUS_PROCESSING
                self.updateQueueTable()
                
                # Перезапускаем кодирование этого файла
                self.processNextInQueue()
            else:
                QMessageBox.warning(self, "Ошибка", "Не удалось определить файл для возобновления")
                self.isPaused = False
                return
        else:
            # На Linux/Mac возобновляем процесс
            try:
                import signal
                os.kill(self.ffmpegProcess.processId(), signal.SIGCONT)
            except Exception as e:
                QMessageBox.warning(self, "Ошибка", 
                    f"Не удалось возобновить процесс: {str(e)}")
                return
        
        self.isPaused = False
        if hasattr(self.ui, 'pauseResumeButton'):
            self.ui.pauseResumeButton.setText("⏸ Пауза")
        self.updateStatus("Выполняется...")

    def _getVideoDuration(self):
        """Получает длительность видео через FFprobe"""
        item = self.getSelectedQueueItem()
        if item:
            self._getVideoDurationForItem(item)
    
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
