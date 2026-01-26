import sys
import os
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
        self.resize(700, 550)

        self.ffmpegProcess = QProcess(self)
        self.presetManager = PresetManager()
        self.inputFile = ""

        # Подключение сигналов
        self.ui.browseButton.clicked.connect(self.selectInputFile)
        self.ui.codecCombo.currentIndexChanged.connect(self.updateCommandFromGUI)
        self.ui.containerCombo.currentIndexChanged.connect(self.updateCommandFromGUI)
        self.ui.resolutionCombo.currentIndexChanged.connect(self.updateCustomResolutionVisibility)
        self.ui.resolutionCombo.currentIndexChanged.connect(self.updateCommandFromGUI)
        self.ui.customResolutionEdit.textChanged.connect(self.updateCommandFromGUI)
        self.ui.runButton.clicked.connect(self.runEncoding)
        self.ui.savePresetButton.clicked.connect(self.savePreset)
        self.ui.loadPresetButton.clicked.connect(self.loadPreset)
        self.ui.deletePresetButton.clicked.connect(self.deletePreset)
        self.ui.copyCmdButton.clicked.connect(self.copyCommand)

        self.ffmpegProcess.readyReadStandardOutput.connect(self.readProcessOutput)
        self.ffmpegProcess.readyReadStandardError.connect(self.readProcessOutput)
        self.ffmpegProcess.finished.connect(self.processFinished)

    def selectInputFile(self):
        self.inputFile = QFileDialog.getOpenFileName(self, "Выберите видео", "", "Видео (*.mp4 *.mkv *.avi)")[0]
        if self.inputFile:
            self.ui.inputFileEdit.setText(self.inputFile)
            self.updateCommandFromGUI()

    def updateCustomResolutionVisibility(self):
        isCustom = self.ui.resolutionCombo.currentText() == "custom"
        self.ui.customResolutionEdit.setVisible(isCustom)
        if isCustom and not self.ui.customResolutionEdit.text():
            self.ui.customResolutionEdit.setText("1920:1080")
        self.updateCommandFromGUI()

    def updateCommandFromGUI(self):
        self.ui.commandDisplay.setPlainText(self.generateFFmpegCommand())

    def generateFFmpegCommand(self):
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

        input_path = os.path.dirname(self.inputFile)
        input_base = os.path.splitext(os.path.basename(self.inputFile))[0]
        base_output = os.path.join(input_path, input_base + "_converted")
        output_file = base_output + "." + container

        # Уникальное имя выходного файла
        counter = 1
        final_output = output_file
        while os.path.exists(final_output):
            final_output = base_output + "_" + str(counter) + "." + container
            counter += 1

        args = ["ffmpeg", "-i", self.inputFile]
        if scale and codec != "copy":
            args += ["-vf", scale]
        if codec != "copy":
            args += ["-c:v", codec]
        args += [final_output]

        return " ".join(args)

    def runEncoding(self):
        if self.ffmpegProcess.state() != QProcess.NotRunning:
            QMessageBox.information(self, "Ожидание", "Дождитесь завершения текущего кодирования")
            return

        newCmd = self.generateFFmpegCommand()
        self.ui.commandDisplay.setPlainText(newCmd)

        args = newCmd.split()[1:]  # Убираем "ffmpeg"

        # Проверка -i
        try:
            iIdx = args.index("-i")
            if iIdx + 1 >= len(args):
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "Ошибка", "Не указан входной файл после -i")
            return

        input_file = args[iIdx + 1]
        if not os.path.exists(input_file):
            QMessageBox.critical(self, "Ошибка", "Файл не существует:\n" + input_file)
            return

        self.ui.logDisplay.clear()
        self.ui.logDisplay.append("<b>Запуск:</b> " + newCmd.replace('<', '&lt;').replace('>', '&gt;') + "<br>")

        self.ui.runButton.setEnabled(False)
        self.ffmpegProcess.start("ffmpeg", args)

    def readProcessOutput(self):
        out = self.ffmpegProcess.readAllStandardOutput().data().decode('utf-8', errors='replace').strip()
        err = self.ffmpegProcess.readAllStandardError().data().decode('utf-8', errors='replace').strip()
        if out:
            self.ui.logDisplay.append(f"<font color='blue'>{out}</font>")
        if err:
            self.ui.logDisplay.append(f"<font color='red'>{err}</font>")

    def processFinished(self, exitCode, exitStatus):
        self.ui.runButton.setEnabled(True)
        self.ui.logDisplay.append(f"<br><b>Готово! Код: {exitCode}</b>")
        if exitCode == 0:
            self.ui.logDisplay.append("<font color='green'>Успешно!</font>")
        else:
            self.ui.logDisplay.append("<font color='red'>Ошибка.</font>")

    def savePreset(self):
        name, ok = QInputDialog.getText(self, "Сохранить", "Имя:", text="default")
        if not ok or not name:
            return
        codec = self.ui.codecCombo.currentText()
        resolution = self.ui.resolutionCombo.currentText()
        container = self.ui.containerCombo.currentText()
        self.presetManager.savePreset(name, codec, resolution, container)
        QMessageBox.information(self, "OK", f"Пресет \"{name}\" сохранён")

    def loadPreset(self):
        names = self.presetManager.presetNames()
        if not names:
            QMessageBox.information(self, "Пресеты", "Нет сохранённых пресетов")
            return
        selected, ok = QInputDialog.getItem(self, "Загрузить пресет", "Выберите пресет:", names, 0, False)
        if not ok or not selected:
            return
        preset = self.presetManager.loadPreset(selected)
        if not preset:
            QMessageBox.warning(self, "Ошибка", "Не удалось загрузить пресет")
            return
        self.ui.codecCombo.setCurrentText(preset['codec'])
        self.ui.resolutionCombo.setCurrentText(preset['resolution'])
        self.ui.containerCombo.setCurrentText(preset['container'])
        self.updateCustomResolutionVisibility()
        self.updateCommandFromGUI()
        QMessageBox.information(self, "Успех", f"Пресет \"{selected}\" загружен")

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
