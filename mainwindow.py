import sys
import os
import platform
import shlex
from PySide6.QtWidgets import QMainWindow, QFileDialog, QMessageBox, QInputDialog
from PySide6.QtCore import QProcess
from PySide6.QtGui import QGuiApplication
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

        self.ffmpegProcess.readyReadStandardOutput.connect(self.readProcessOutput)
        self.ffmpegProcess.readyReadStandardError.connect(self.readProcessOutput)
        self.ffmpegProcess.finished.connect(self.processFinished)
        
        # Инициализация статуса
        self.updateStatus("Готов")

    def selectInputFile(self):
        self.inputFile = QFileDialog.getOpenFileName(self, "Выберите видео", "", "Видео (*.mp4 *.mkv *.avi)")[0]
        if self.inputFile:
            self.ui.inputFileEdit.setText(self.inputFile)
            self.commandManuallyEdited = False  # Сбрасываем флаг при выборе нового файла
            self.updateCommandFromGUI()

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
        if err:
            self._appendLog(err, 'error')
    
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

    def processFinished(self, exitCode, exitStatus):
        self.ui.runButton.setEnabled(True)
        
        if exitCode == 0:
            self.updateStatus("Завершено успешно")
            self.ui.logDisplay.append(f"<br><b><font color='green'>✓ Готово! Кодирование завершено успешно.</font></b>")
            # Показываем кнопку открытия папки, если она есть
            if hasattr(self.ui, 'openOutputFolderButton'):
                self.ui.openOutputFolderButton.setEnabled(True)
        else:
            self.updateStatus("Ошибка")
            self.ui.logDisplay.append(f"<br><b><font color='red'>✗ Ошибка! Код завершения: {exitCode}</font></b>")
    
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
