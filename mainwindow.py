import sys
import os
import platform
import shlex
import re
from PySide6.QtWidgets import QMainWindow, QFileDialog, QMessageBox, QInputDialog, QVBoxLayout
from PySide6.QtCore import QProcess, QUrl, Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from ui_mainwindow import Ui_MainWindow  # Сгенерированный из .ui интерфейс
from presetmanager import PresetManager

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle("OpenFF GUI - MVP")
        self.resize(900, 750)

        self.ffmpegProcess = QProcess(self)
        self.presetManager = PresetManager()
        self.inputFile = ""
        self.lastOutputFile = ""  # Сохраняем путь к последнему выходному файлу
        self.commandManuallyEdited = False  # Флаг ручного редактирования команды
        self.lastGeneratedCommand = ""  # Последняя сгенерированная команда
        
        # Переменные для прогресса кодирования
        self.encodingProgress = 0  # 0-100
        self.totalFrames = 0  # Общее количество кадров
        self.currentFrame = 0  # Текущий кадр
        self.videoDuration = 0  # Длительность видео в секундах
        self.encodingDuration = 0  # Длительность кодирования в секундах
        self.isPaused = False  # Флаг паузы
        
        # Инициализация медиаплеера для предпросмотра
        self.initVideoPreview()

        # Подключение сигналов
        self.ui.browseButton.clicked.connect(self.selectInputFile)
        self.ui.codecCombo.currentIndexChanged.connect(self.updateCommandFromGUI)
        self.ui.containerCombo.currentIndexChanged.connect(self.updateCommandFromGUI)
        self.ui.resolutionCombo.currentIndexChanged.connect(self.updateCustomResolutionVisibility)
        self.ui.resolutionCombo.currentIndexChanged.connect(self.updateCommandFromGUI)
        self.ui.customResolutionEdit.textChanged.connect(self.updateCommandFromGUI)
        self.ui.commandDisplay.textChanged.connect(self.onCommandManuallyEdited)
        self.ui.runButton.clicked.connect(self.runEncoding)
        self.ui.savePresetButton.clicked.connect(self.savePreset)
        self.ui.loadPresetButton.clicked.connect(self.loadPreset)
        self.ui.deletePresetButton.clicked.connect(self.deletePreset)
        self.ui.exportPresetButton.clicked.connect(self.exportPreset)
        self.ui.importPresetButton.clicked.connect(self.importPreset)
        self.ui.copyCmdButton.clicked.connect(self.copyCommand)
        self.ui.openOutputFolderButton.clicked.connect(self.openOutputFolder)
        
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
    
    def selectInputFile(self):
        self.inputFile = QFileDialog.getOpenFileName(self, "Выберите видео", "", "Видео (*.mp4 *.mkv *.avi)")[0]
        if self.inputFile:
            self.ui.inputFileEdit.setText(self.inputFile)
            self.commandManuallyEdited = False  # Сбрасываем флаг при выборе нового файла
            self.updateCommandFromGUI()
            # Загружаем видео в предпросмотр
            self.loadVideoForPreview()

    def updateCustomResolutionVisibility(self):
        isCustom = self.ui.resolutionCombo.currentText() == "custom"
        self.ui.customResolutionEdit.setVisible(isCustom)
        if isCustom and not self.ui.customResolutionEdit.text():
            self.ui.customResolutionEdit.setText("1920:1080")
        self.updateCommandFromGUI()

    def updateCommandFromGUI(self):
        """Обновляет команду только если она не была отредактирована вручную"""
        if not self.commandManuallyEdited:
            new_cmd = self.generateFFmpegCommand()
            self.lastGeneratedCommand = new_cmd
            self.ui.commandDisplay.setPlainText(new_cmd)
    
    def onCommandManuallyEdited(self):
        """Отслеживает ручное редактирование команды"""
        current_cmd = self.ui.commandDisplay.toPlainText()
        if current_cmd != self.lastGeneratedCommand:
            self.commandManuallyEdited = True

    def _quotePath(self, path):
        """Оборачивает путь в кавычки, если он содержит пробелы или специальные символы"""
        if ' ' in path or '[' in path or ']' in path or '(' in path or ')' in path:
            return f'"{path}"'
        return path
    
    def generateFFmpegCommand(self):
        """Генерирует команду FFmpeg и возвращает строку для отображения"""
        if not self.inputFile:
            return "ffmpeg"

        codec = self.ui.codecCombo.currentText()
        container = self.ui.containerCombo.currentText()
        res = self.ui.resolutionCombo.currentText()

        scale = ""
        if res == "480p":
            scale = "scale=854:480"
        elif res == "720p":
            scale = "scale=1280:720"
        elif res == "1080p":
            scale = "scale=1920:1080"
        elif res == "custom":
            custom = self.ui.customResolutionEdit.text().strip()
            if ':' in custom:
                scale = "scale=" + custom

        # Нормализуем входной путь
        input_file_normalized = os.path.normpath(self.inputFile)
        input_path = os.path.dirname(input_file_normalized)
        input_base = os.path.splitext(os.path.basename(input_file_normalized))[0]
        base_output = os.path.join(input_path, input_base + "_converted")
        output_file = base_output + "." + container

        # Уникальное имя выходного файла
        counter = 1
        final_output = output_file
        while os.path.exists(final_output):
            final_output = base_output + "_" + str(counter) + "." + container
            counter += 1
        
        # Нормализуем выходной путь
        final_output = os.path.normpath(final_output)
        
        # Сохраняем путь к выходному файлу для возможности открыть папку
        self.lastOutputFile = final_output

        # Формируем команду для отображения (с кавычками вокруг путей)
        cmd_parts = ["ffmpeg", "-i", self._quotePath(input_file_normalized)]
        if scale and codec != "copy":
            cmd_parts += ["-vf", scale]
        if codec != "copy":
            cmd_parts += ["-c:v", codec]
        cmd_parts.append(self._quotePath(final_output))

        return " ".join(cmd_parts)
    
    def _getFFmpegArgs(self):
        """Возвращает список аргументов для запуска FFmpeg (без кавычек, для QProcess)"""
        if not self.inputFile:
            return []

        codec = self.ui.codecCombo.currentText()
        container = self.ui.containerCombo.currentText()
        res = self.ui.resolutionCombo.currentText()

        scale = ""
        if res == "480p":
            scale = "scale=854:480"
        elif res == "720p":
            scale = "scale=1280:720"
        elif res == "1080p":
            scale = "scale=1920:1080"
        elif res == "custom":
            custom = self.ui.customResolutionEdit.text().strip()
            if ':' in custom:
                scale = "scale=" + custom

        # Нормализуем входной путь
        input_file_normalized = os.path.normpath(self.inputFile)
        input_path = os.path.dirname(input_file_normalized)
        input_base = os.path.splitext(os.path.basename(input_file_normalized))[0]
        base_output = os.path.join(input_path, input_base + "_converted")
        output_file = base_output + "." + container

        # Уникальное имя выходного файла
        counter = 1
        final_output = output_file
        while os.path.exists(final_output):
            final_output = base_output + "_" + str(counter) + "." + container
            counter += 1
        
        # Нормализуем выходной путь
        final_output = os.path.normpath(final_output)
        
        # Сохраняем путь к выходному файлу
        self.lastOutputFile = final_output

        # Формируем список аргументов (без кавычек, QProcess сам обработает пробелы)
        args = ["-i", input_file_normalized]
        if scale and codec != "copy":
            args += ["-vf", scale]
        if codec != "copy":
            args += ["-c:v", codec]
        args.append(final_output)

        return args

    def runEncoding(self):
        if self.ffmpegProcess.state() != QProcess.NotRunning:
            QMessageBox.information(self, "Ожидание", "Дождитесь завершения текущего кодирования")
            return

        # Получаем команду из поля (может быть отредактирована вручную)
        cmd_from_display = self.ui.commandDisplay.toPlainText().strip()
        
        if not cmd_from_display or cmd_from_display == "ffmpeg":
            QMessageBox.warning(self, "Ошибка", "Команда не может быть пустой")
            return

        # Парсим команду из текстового поля
        try:
            args = self._parseCommand(cmd_from_display)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Неверный формат команды:\n{str(e)}")
            return

        # Проверка наличия входного файла
        try:
            i_idx = args.index("-i")
            if i_idx + 1 >= len(args):
                raise ValueError("Не указан входной файл после -i")
            input_file = args[i_idx + 1]
            if not os.path.exists(input_file):
                QMessageBox.critical(self, "Ошибка", f"Входной файл не существует:\n{input_file}")
                return
        except (ValueError, IndexError):
            QMessageBox.warning(self, "Ошибка", "Не указан входной файл")
            return

        # Определяем выходной файл из команды
        if len(args) > 0:
            # Последний аргумент обычно выходной файл
            potential_output = args[-1]
            if os.path.isabs(potential_output) or not potential_output.startswith('-'):
                self.lastOutputFile = os.path.normpath(potential_output)

        self.ui.logDisplay.clear()
        self.updateStatus("Выполняется...")
        self.ui.logDisplay.append("<b>Запуск:</b> " + cmd_from_display.replace('<', '&lt;').replace('>', '&gt;') + "<br>")

        self.ui.runButton.setEnabled(False)
        # Отключаем кнопку открытия папки до завершения
        if hasattr(self.ui, 'openOutputFolderButton'):
            self.ui.openOutputFolderButton.setEnabled(False)
        
        # Активируем кнопку паузы
        if hasattr(self.ui, 'pauseResumeButton'):
            self.ui.pauseResumeButton.setEnabled(True)
            self.ui.pauseResumeButton.setText("⏸ Пауза")
        
        # Сбрасываем прогресс
        self.encodingProgress = 0
        self.currentFrame = 0
        self.encodingDuration = 0
        if hasattr(self.ui, 'encodingProgressBar'):
            self.ui.encodingProgressBar.setValue(0)
        
        # Получаем длительность видео для расчёта прогресса
        if self.mediaPlayer and self.inputFile:
            # Пытаемся получить длительность из медиаплеера
            if self.videoDuration <= 0:
                # Если длительность неизвестна, пытаемся получить через FFprobe
                self._getVideoDuration()
        
        # Запускаем FFmpeg с аргументами из команды
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
        # FFmpeg выводит прогресс в формате: frame=  123 fps= 25 q=28.0 size=    1024kB time=00:00:05.00 bitrate= 1638.4kbits/s
        # Ищем frame= и time=
        
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
        
        # Обновляем прогресс
        self.updateEncodingProgress()
    
    def updateEncodingProgress(self):
        """Обновляет прогресс-бар и таймлайн на основе текущего прогресса"""
        if self.videoDuration > 0 and self.encodingDuration > 0:
            # Вычисляем процент прогресса
            progress = min(100, int((self.encodingDuration / self.videoDuration) * 100))
            self.encodingProgress = progress
            
            # Обновляем прогресс-бар
            if hasattr(self.ui, 'encodingProgressBar'):
                self.ui.encodingProgressBar.setValue(progress)
            
            # Обновляем таймлайн предпросмотра (если есть)
            if hasattr(self.ui, 'videoTimelineSlider') and self.videoDuration > 0:
                # Обновляем только если не происходит ручная перемотка
                if not self.ui.videoTimelineSlider.isSliderDown():
                    max_value = self.ui.videoTimelineSlider.maximum()
                    timeline_position = int((self.encodingDuration / self.videoDuration) * max_value)
                    self.ui.videoTimelineSlider.setValue(timeline_position)
    
    def loadVideoForPreview(self):
        """Загружает видео в медиаплеер для предпросмотра"""
        if not self.mediaPlayer or not self.inputFile:
            return
        
        try:
            # Загружаем видео
            url = QUrl.fromLocalFile(self.inputFile)
            self.mediaPlayer.setSource(url)
            
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
        
        self.isPaused = True
        
        # Сохраняем текущую команду для возобновления
        self.pausedCommand = self.ui.commandDisplay.toPlainText()
        self.pausedArgs = self._parseCommand(self.pausedCommand)
        
        # Пытаемся приостановить процесс через сигналы
        try:
            if platform.system() == "Windows":
                # На Windows QProcess не поддерживает SIGSTOP напрямую
                # Используем альтернативный метод через приостановку потоков
                # Это требует дополнительных библиотек (pywin32) или ctypes
                # Для упрощения показываем предупреждение
                QMessageBox.information(self, "Информация", 
                    "Пауза кодирования на Windows работает через остановку процесса.\n"
                    "При возобновлении кодирование начнётся заново.")
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
                    return
        except Exception as e:
            QMessageBox.warning(self, "Предупреждение", 
                f"Ошибка при паузе: {str(e)}")
            self.isPaused = False
            return
        
        if hasattr(self.ui, 'pauseResumeButton'):
            self.ui.pauseResumeButton.setText("▶ Возобновить")
        self.updateStatus("Приостановлено...")
    
    def resumeEncoding(self):
        """Возобновляет кодирование"""
        if not self.isPaused:
            return
        
        try:
            if platform.system() == "Windows":
                # На Windows перезапускаем процесс с сохранённой командой
                # Это не идеально, но работает
                if hasattr(self, 'pausedArgs') and self.pausedArgs:
                    self.ffmpegProcess.start("ffmpeg", self.pausedArgs)
                else:
                    QMessageBox.warning(self, "Ошибка", "Не удалось восстановить команду")
                    self.isPaused = False
                    return
            else:
                # На Linux/Mac используем SIGCONT
                import signal
                try:
                    os.kill(self.ffmpegProcess.processId(), signal.SIGCONT)
                except (ProcessLookupError, PermissionError) as e:
                    QMessageBox.warning(self, "Ошибка", 
                        f"Не удалось возобновить процесс: {str(e)}")
                    return
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", 
                f"Ошибка при возобновлении: {str(e)}")
            return
        
        self.isPaused = False
        if hasattr(self.ui, 'pauseResumeButton'):
            self.ui.pauseResumeButton.setText("⏸ Пауза")
        self.updateStatus("Выполняется...")

    def _getVideoDuration(self):
        """Получает длительность видео через FFprobe"""
        if not self.inputFile:
            return
        
        try:
            import subprocess
            # Используем ffprobe для получения длительности
            cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', 
                   '-of', 'default=noprint_wrappers=1:nokey=1', self.inputFile]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                duration_str = result.stdout.strip()
                if duration_str:
                    self.videoDuration = float(duration_str)
        except Exception as e:
            print(f"Не удалось получить длительность видео: {e}")
    
    def processFinished(self, exitCode, exitStatus):
        self.ui.runButton.setEnabled(True)
        
        # Отключаем кнопку паузы
        if hasattr(self.ui, 'pauseResumeButton'):
            self.ui.pauseResumeButton.setEnabled(False)
            self.ui.pauseResumeButton.setText("⏸ Пауза")
        
        # Сбрасываем прогресс
        if hasattr(self.ui, 'encodingProgressBar'):
            self.ui.encodingProgressBar.setValue(100 if exitCode == 0 else 0)
        
        if exitCode == 0:
            self.updateStatus("Завершено успешно")
            self.ui.logDisplay.append(f"<br><b><font color='green'>✓ Готово! Кодирование завершено успешно.</font></b>")
            # Показываем кнопку открытия папки, если она есть
            if hasattr(self.ui, 'openOutputFolderButton'):
                self.ui.openOutputFolderButton.setEnabled(True)
        else:
            self.updateStatus("Ошибка")
            self.ui.logDisplay.append(f"<br><b><font color='red'>✗ Ошибка! Код завершения: {exitCode}</font></b>")
        
        self.isPaused = False
    
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

    def savePreset(self):
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QTextEdit, QDialogButtonBox
        
        # Создаём диалог для ввода имени и описания
        dialog = QDialog(self)
        dialog.setWindowTitle("Сохранить пресет")
        dialog.setMinimumWidth(400)
        
        layout = QVBoxLayout(dialog)
        
        name_label = QLabel("Имя пресета:")
        name_edit = QLineEdit()
        name_edit.setText("default")
        name_edit.selectAll()
        
        desc_label = QLabel("Описание (необязательно):")
        desc_edit = QTextEdit()
        desc_edit.setMaximumHeight(100)
        desc_edit.setPlaceholderText("Введите описание пресета...")
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        
        layout.addWidget(name_label)
        layout.addWidget(name_edit)
        layout.addWidget(desc_label)
        layout.addWidget(desc_edit)
        layout.addWidget(buttons)
        
        if dialog.exec() != QDialog.Accepted:
            return
        
        name = name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Ошибка", "Имя пресета не может быть пустым")
            return
        
        description = desc_edit.toPlainText().strip()
        codec = self.ui.codecCombo.currentText()
        resolution = self.ui.resolutionCombo.currentText()
        container = self.ui.containerCombo.currentText()
        
        self.presetManager.savePreset(name, codec, resolution, container, description)
        QMessageBox.information(self, "OK", f"Пресет \"{name}\" сохранён")

    def loadPreset(self):
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QListWidget, QTextEdit, QDialogButtonBox
        
        names = self.presetManager.presetNames()
        if not names:
            QMessageBox.information(self, "Пресеты", "Нет сохранённых пресетов")
            return
        
        # Создаём диалог для выбора пресета с отображением описания
        dialog = QDialog(self)
        dialog.setWindowTitle("Загрузить пресет")
        dialog.setMinimumWidth(500)
        dialog.setMinimumHeight(300)
        
        layout = QVBoxLayout(dialog)
        
        list_label = QLabel("Выберите пресет:")
        preset_list = QListWidget()
        preset_list.addItems(names)
        preset_list.setCurrentRow(0)
        
        desc_label = QLabel("Описание:")
        desc_display = QTextEdit()
        desc_display.setReadOnly(True)
        desc_display.setMaximumHeight(80)
        
        # Обновляем описание при выборе пресета
        def updateDescription():
            selected = preset_list.currentItem()
            if selected:
                preset = self.presetManager.loadPreset(selected.text())
                if preset and preset.get('description'):
                    desc_display.setPlainText(preset['description'])
                else:
                    desc_display.setPlainText("(нет описания)")
        
        preset_list.currentItemChanged.connect(lambda: updateDescription())
        updateDescription()  # Инициализация
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        
        layout.addWidget(list_label)
        layout.addWidget(preset_list)
        layout.addWidget(desc_label)
        layout.addWidget(desc_display)
        layout.addWidget(buttons)
        
        if dialog.exec() != QDialog.Accepted:
            return
        
        selected_item = preset_list.currentItem()
        if not selected_item:
            return
        
        selected = selected_item.text()
        preset = self.presetManager.loadPreset(selected)
        if not preset:
            QMessageBox.warning(self, "Ошибка", "Не удалось загрузить пресет")
            return
        
        self.ui.codecCombo.setCurrentText(preset['codec'])
        self.ui.resolutionCombo.setCurrentText(preset['resolution'])
        self.ui.containerCombo.setCurrentText(preset['container'])
        self.commandManuallyEdited = False  # Сбрасываем флаг при загрузке пресета
        self.updateCustomResolutionVisibility()
        self.updateCommandFromGUI()
        
        msg = f"Пресет \"{selected}\" загружен"
        if preset.get('description'):
            msg += f"\n\nОписание: {preset['description']}"
        QMessageBox.information(self, "Успех", msg)

    def deletePreset(self):
        names = self.presetManager.presetNames()
        if not names:
            QMessageBox.information(self, "Пресеты", "Нет пресетов для удаления")
            return
        selected, ok = QInputDialog.getItem(self, "Удалить пресет", "Выберите пресет для удаления:", names, 0, False)
        if not ok or not selected:
            return
        ret = QMessageBox.question(self, "Подтверждение", f"Удалить пресет \"{selected}\"?\n\nЭто действие нельзя отменить.", QMessageBox.Yes | QMessageBox.No)
        if ret == QMessageBox.Yes:
            self.presetManager.removePreset(selected)
            QMessageBox.information(self, "Удалено", f"Пресет \"{selected}\" удалён")

    def copyCommand(self):
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(self.ui.commandDisplay.toPlainText())
        QMessageBox.information(self, "Скопировано", "Команда скопирована в буфер обмена!")
    
    def exportPreset(self):
        """Экспортирует выбранный пресет в XML файл"""
        names = self.presetManager.presetNames()
        if not names:
            QMessageBox.information(self, "Пресеты", "Нет пресетов для экспорта")
            return
        
        # Выбор пресета для экспорта
        selected, ok = QInputDialog.getItem(self, "Экспорт пресета", "Выберите пресет для экспорта:", names, 0, False)
        if not ok or not selected:
            return
        
        # Выбор места сохранения файла
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Экспорт пресета", 
            f"{selected}.xml", 
            "XML файлы (*.xml)"
        )
        
        if not file_path:
            return
        
        # Загружаем пресет
        preset = self.presetManager.loadPreset(selected)
        if not preset:
            QMessageBox.warning(self, "Ошибка", "Не удалось загрузить пресет")
            return
        
        # Создаём XML структуру
        import xml.etree.ElementTree as ET
        root = ET.Element('preset')
        root.set('name', selected)
        ET.SubElement(root, 'codec').text = preset['codec']
        ET.SubElement(root, 'resolution').text = preset['resolution']
        ET.SubElement(root, 'container').text = preset['container']
        desc_elem = ET.SubElement(root, 'description')
        desc_elem.text = preset.get('description', '')
        
        # Сохраняем в файл
        tree = ET.ElementTree(root)
        tree.write(file_path, encoding='utf-8', xml_declaration=True)
        
        QMessageBox.information(self, "Успех", f"Пресет \"{selected}\" экспортирован в:\n{file_path}")
    
    def importPreset(self):
        """Импортирует пресет из XML файла"""
        # Выбор файла для импорта
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Импорт пресета",
            "",
            "XML файлы (*.xml)"
        )
        
        if not file_path:
            return
        
        # Читаем XML файл
        import xml.etree.ElementTree as ET
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            if root.tag != 'preset':
                QMessageBox.warning(self, "Ошибка", "Неверный формат файла пресета")
                return
            
            # Извлекаем данные
            name = root.get('name', 'imported_preset')
            codec_elem = root.find('codec')
            resolution_elem = root.find('resolution')
            container_elem = root.find('container')
            desc_elem = root.find('description')
            
            if codec_elem is None or resolution_elem is None or container_elem is None:
                QMessageBox.warning(self, "Ошибка", "Файл пресета повреждён или неполный")
                return
            
            codec = codec_elem.text
            resolution = resolution_elem.text
            container = container_elem.text
            description = desc_elem.text if desc_elem is not None and desc_elem.text else ""
            
            # Проверяем, существует ли пресет с таким именем
            existing_names = self.presetManager.presetNames()
            if name in existing_names:
                ret = QMessageBox.question(
                    self,
                    "Пресет существует",
                    f"Пресет с именем \"{name}\" уже существует.\nПерезаписать?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if ret != QMessageBox.Yes:
                    return
            
            # Сохраняем пресет
            self.presetManager.savePreset(name, codec, resolution, container, description)
            QMessageBox.information(self, "Успех", f"Пресет \"{name}\" успешно импортирован!")
            
        except ET.ParseError:
            QMessageBox.critical(self, "Ошибка", "Не удалось прочитать XML файл")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при импорте:\n{str(e)}")
