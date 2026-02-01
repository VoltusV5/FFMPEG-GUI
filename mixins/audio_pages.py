"""Миксин: вкладки «Видео в аудио» и «Аудио конвертер»."""

import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QMessageBox, QButtonGroup, QProgressBar,
)
from PySide6.QtCore import QProcess

from app.constants import (
    AUDIO_FORMATS, AUDIO_QUALITY_OPTIONS, AUDIO_CODEC_MAP,
    STYLE_CONVERT_BUTTON, PROGRESS_MIN, PROGRESS_MAX,
)
from widgets import FileDropArea


class AudioPagesMixin:
    """Миксин: страницы «Видео в аудио» и «Аудио конвертер» — один файл, конвертация в аудио."""

    def _computeOutputPathForExtension(self, input_path, ext):
        """Строит выходной путь: та же папка, то же имя с новым расширением; при коллизии добавляет (1), (2)…"""
        if not input_path or not ext:
            return ""
        base = os.path.splitext(os.path.basename(input_path))[0]
        dir_path = os.path.dirname(input_path)
        out_path = os.path.normpath(os.path.join(dir_path, base + "." + ext))
        counter = 0
        while os.path.exists(out_path):
            counter += 1
            out_path = os.path.normpath(os.path.join(dir_path, f"{base} ({counter})." + ext))
        return out_path

    def _createVideoToAudioPage(self):
        """Создаёт страницу «Перекодировать видео в аудио». Минимальный функционал: один файл, без очереди."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        title = QLabel("Перекодировать видео в аудио")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)

        v2a_exts = {".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv", ".webm"}
        self._v2aDropArea = FileDropArea(self._v2aBrowseInput, self._v2aSetInputPath, v2a_exts, page)
        layout.addWidget(self._v2aDropArea)

        input_row = QHBoxLayout()
        input_row.addWidget(QLabel("Входной файл:"))
        self._v2aInputEdit = QLineEdit()
        self._v2aInputEdit.setReadOnly(True)
        self._v2aInputEdit.setPlaceholderText("Выберите видеофайл...")
        input_row.addWidget(self._v2aInputEdit)
        btn_browse = QPushButton("Обзор...")
        btn_browse.clicked.connect(self._v2aBrowseInput)
        input_row.addWidget(btn_browse)
        layout.addLayout(input_row)

        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("Выходной файл:"))
        self._v2aOutputEdit = QLineEdit()
        self._v2aOutputEdit.setReadOnly(True)
        self._v2aOutputEdit.setPlaceholderText("—")
        out_row.addWidget(self._v2aOutputEdit)
        layout.addLayout(out_row)

        format_row = QHBoxLayout()
        format_row.addWidget(QLabel("Формат:"))
        self._v2aFormatGroup = QButtonGroup(page)
        for name, ext in AUDIO_FORMATS:
            btn = QPushButton(name)
            btn.setCheckable(True)
            self._v2aFormatGroup.addButton(btn)
            format_row.addWidget(btn)
        self._v2aFormatGroup.buttons()[0].setChecked(True)
        self._v2aFormatGroup.buttonClicked.connect(lambda: self._v2aUpdateOutputPath())
        layout.addLayout(format_row)

        quality_row = QHBoxLayout()
        quality_row.addWidget(QLabel("Качество:"))
        self._v2aQualityGroup = QButtonGroup(page)
        for text, val in AUDIO_QUALITY_OPTIONS:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setProperty("v2a_quality", val)
            self._v2aQualityGroup.addButton(btn)
            quality_row.addWidget(btn)
        self._v2aQualityGroup.buttons()[0].setChecked(True)
        self._v2aQualityGroup.buttonClicked.connect(lambda: self._v2aUpdateOutputPath())
        layout.addLayout(quality_row)

        self._v2aProgressBar = QProgressBar()
        self._v2aProgressBar.setVisible(False)
        layout.addWidget(self._v2aProgressBar)

        btn_row = QHBoxLayout()
        self._v2aConvertBtn = QPushButton("Конвертировать")
        self._v2aConvertBtn.setStyleSheet(STYLE_CONVERT_BUTTON)
        self._v2aConvertBtn.clicked.connect(self._v2aConvert)
        btn_row.addWidget(self._v2aConvertBtn)
        self._v2aOpenFolderBtn = QPushButton("Открыть в папке")
        self._v2aOpenFolderBtn.setEnabled(False)
        self._v2aOpenFolderBtn.clicked.connect(self._v2aOpenFolder)
        btn_row.addWidget(self._v2aOpenFolderBtn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._v2aLastOutputPath = ""
        self._v2aProcess = QProcess(self)
        self._v2aProcess.finished.connect(self._v2aProcessFinished)
        self._v2aProcess.readyReadStandardError.connect(self._v2aReadProcessOutput)
        self._v2aProcess.readyReadStandardOutput.connect(self._v2aReadProcessOutput)

        layout.addStretch()
        return page

    def _v2aGetFormat(self):
        btn = self._v2aFormatGroup.checkedButton()
        if not btn:
            return "mp3"
        text = btn.text().lower()
        return {"mp3": "mp3", "wav": "wav", "m4a": "m4a", "flac": "flac", "ogg": "ogg"}.get(text, "mp3")

    def _v2aGetQuality(self):
        btn = self._v2aQualityGroup.checkedButton()
        if not btn:
            return "copy"
        return btn.property("v2a_quality") or "copy"

    def _v2aBrowseInput(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите видеофайл",
            "",
            "Видео (*.mp4 *.mkv *.avi *.mov *.flv *.wmv *.webm)"
        )
        if path:
            self._v2aSetInputPath(path)

    def _v2aSetInputPath(self, path):
        if not path:
            return
        self._v2aInputEdit.setText(path)
        self._v2aUpdateOutputPath()
        self._v2aOpenFolderBtn.setEnabled(False)
        self._v2aProgressBar.setVisible(False)

    def _v2aUpdateOutputPath(self):
        inp = self._v2aInputEdit.text().strip()
        if not inp or not os.path.isfile(inp):
            self._v2aOutputEdit.setText("")
            return
        ext = self._v2aGetFormat()
        self._v2aOutputEdit.setText(self._computeOutputPathForExtension(inp, ext))

    def _v2aConvert(self):
        inp = self._v2aInputEdit.text().strip()
        if not inp or not os.path.isfile(inp):
            QMessageBox.warning(self, "Видео в аудио", "Выберите входной видеофайл.")
            return
        out = self._v2aOutputEdit.text().strip()
        if not out:
            self._v2aUpdateOutputPath()
            out = self._v2aOutputEdit.text().strip()
        if not out:
            QMessageBox.warning(self, "Видео в аудио", "Не удалось определить выходной файл.")
            return
        fmt = self._v2aGetFormat()
        quality = self._v2aGetQuality()
        codec = AUDIO_CODEC_MAP.get(fmt, "libmp3lame")
        args = ["-y", "-i", os.path.normpath(inp), "-vn", "-c:a", codec]
        if quality != "copy":
            args.extend(["-b:a", quality + "k"])
        args.append(os.path.normpath(out))

        self._v2aConvertBtn.setEnabled(False)
        self._v2aLastOutputPath = out
        self._v2aProgressBar.setVisible(True)
        self._v2aProgressBar.setRange(0, 0)
        self._v2aProcess.start("ffmpeg", args)

    def _v2aReadProcessOutput(self):
        proc = getattr(self, "_v2aProcess", None)
        if proc and proc == self.sender():
            data = proc.readAllStandardError().data() + proc.readAllStandardOutput().data()
            if data:
                pass

    def _v2aProcessFinished(self, exitCode, exitStatus):
        self._v2aConvertBtn.setEnabled(True)
        self._v2aProgressBar.setRange(PROGRESS_MIN, PROGRESS_MAX)
        self._v2aProgressBar.setValue(PROGRESS_MAX if exitCode == 0 else PROGRESS_MIN)
        if exitCode == 0:
            self._v2aOpenFolderBtn.setEnabled(True)
            QMessageBox.information(self, "Видео в аудио", "Конвертация завершена.")
        else:
            self._v2aOpenFolderBtn.setEnabled(False)
            try:
                if self._v2aLastOutputPath and os.path.exists(self._v2aLastOutputPath):
                    os.remove(self._v2aLastOutputPath)
            except Exception:
                pass
            QMessageBox.warning(self, "Видео в аудио", "Ошибка конвертации.")

    def _v2aOpenFolder(self):
        path = getattr(self, "_v2aLastOutputPath", "") or self._v2aOutputEdit.text().strip()
        if not path:
            QMessageBox.warning(self, "Видео в аудио", "Нет выходного файла.")
            return
        out_dir = os.path.dirname(path)
        if not os.path.isdir(out_dir):
            QMessageBox.warning(self, "Видео в аудио", "Папка не найдена.")
            return
        self._openFolderOrSelectFile(path)

    def _createAudioConverterPage(self):
        """Страница «Аудио конвертер»: аудио → аудио, один файл, без очереди."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        title = QLabel("Аудио конвертер")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)

        a2a_exts = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".wma", ".opus"}
        self._a2aDropArea = FileDropArea(self._a2aBrowseInput, self._a2aSetInputPath, a2a_exts, page)
        layout.addWidget(self._a2aDropArea)

        input_row = QHBoxLayout()
        input_row.addWidget(QLabel("Входной файл:"))
        self._a2aInputEdit = QLineEdit()
        self._a2aInputEdit.setReadOnly(True)
        self._a2aInputEdit.setPlaceholderText("Выберите аудиофайл...")
        input_row.addWidget(self._a2aInputEdit)
        btn_browse = QPushButton("Обзор...")
        btn_browse.clicked.connect(self._a2aBrowseInput)
        input_row.addWidget(btn_browse)
        layout.addLayout(input_row)

        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("Выходной файл:"))
        self._a2aOutputEdit = QLineEdit()
        self._a2aOutputEdit.setReadOnly(True)
        self._a2aOutputEdit.setPlaceholderText("—")
        out_row.addWidget(self._a2aOutputEdit)
        layout.addLayout(out_row)

        format_row = QHBoxLayout()
        format_row.addWidget(QLabel("Формат:"))
        self._a2aFormatGroup = QButtonGroup(page)
        for name, ext in AUDIO_FORMATS:
            btn = QPushButton(name)
            btn.setCheckable(True)
            self._a2aFormatGroup.addButton(btn)
            format_row.addWidget(btn)
        self._a2aFormatGroup.buttons()[0].setChecked(True)
        self._a2aFormatGroup.buttonClicked.connect(lambda: self._a2aUpdateOutputPath())
        layout.addLayout(format_row)

        quality_row = QHBoxLayout()
        quality_row.addWidget(QLabel("Качество:"))
        self._a2aQualityGroup = QButtonGroup(page)
        for text, val in AUDIO_QUALITY_OPTIONS:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setProperty("a2a_quality", val)
            self._a2aQualityGroup.addButton(btn)
            quality_row.addWidget(btn)
        self._a2aQualityGroup.buttons()[0].setChecked(True)
        self._a2aQualityGroup.buttonClicked.connect(lambda: self._a2aUpdateOutputPath())
        layout.addLayout(quality_row)

        self._a2aProgressBar = QProgressBar()
        self._a2aProgressBar.setVisible(False)
        layout.addWidget(self._a2aProgressBar)

        btn_row = QHBoxLayout()
        self._a2aConvertBtn = QPushButton("Конвертировать")
        self._a2aConvertBtn.setStyleSheet(STYLE_CONVERT_BUTTON)
        self._a2aConvertBtn.clicked.connect(self._a2aConvert)
        btn_row.addWidget(self._a2aConvertBtn)
        self._a2aOpenFolderBtn = QPushButton("Открыть в папке")
        self._a2aOpenFolderBtn.setToolTip("Открыть папку с выходным файлом.")
        self._a2aOpenFolderBtn.setEnabled(False)
        self._a2aOpenFolderBtn.clicked.connect(self._a2aOpenFolder)
        btn_row.addWidget(self._a2aOpenFolderBtn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._a2aLastOutputPath = ""
        self._a2aProcess = QProcess(self)
        self._a2aProcess.finished.connect(self._a2aProcessFinished)
        self._a2aProcess.readyReadStandardError.connect(self._a2aReadProcessOutput)
        self._a2aProcess.readyReadStandardOutput.connect(self._a2aReadProcessOutput)

        layout.addStretch()
        return page

    def _a2aGetFormat(self):
        btn = self._a2aFormatGroup.checkedButton()
        if not btn:
            return "mp3"
        text = btn.text().lower()
        return {"mp3": "mp3", "wav": "wav", "m4a": "m4a", "flac": "flac", "ogg": "ogg"}.get(text, "mp3")

    def _a2aGetQuality(self):
        btn = self._a2aQualityGroup.checkedButton()
        if not btn:
            return "copy"
        return btn.property("a2a_quality") or "copy"

    def _a2aBrowseInput(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите аудиофайл",
            "",
            "Аудио (*.mp3 *.wav *.m4a *.flac *.ogg *.aac *.wma *.opus);;Все файлы (*.*)"
        )
        if path:
            self._a2aSetInputPath(path)

    def _a2aSetInputPath(self, path):
        if not path:
            return
        self._a2aInputEdit.setText(path)
        self._a2aUpdateOutputPath()
        self._a2aOpenFolderBtn.setEnabled(False)
        self._a2aProgressBar.setVisible(False)

    def _a2aUpdateOutputPath(self):
        inp = self._a2aInputEdit.text().strip()
        if not inp or not os.path.isfile(inp):
            self._a2aOutputEdit.setText("")
            return
        ext = self._a2aGetFormat()
        self._a2aOutputEdit.setText(self._computeOutputPathForExtension(inp, ext))

    def _a2aConvert(self):
        inp = self._a2aInputEdit.text().strip()
        if not inp or not os.path.isfile(inp):
            QMessageBox.warning(self, "Аудио конвертер", "Выберите входной аудиофайл.")
            return
        out = self._a2aOutputEdit.text().strip()
        if not out:
            self._a2aUpdateOutputPath()
            out = self._a2aOutputEdit.text().strip()
        if not out:
            QMessageBox.warning(self, "Аудио конвертер", "Не удалось определить выходной файл.")
            return
        fmt = self._a2aGetFormat()
        quality = self._a2aGetQuality()
        codec = AUDIO_CODEC_MAP.get(fmt, "libmp3lame")
        args = ["-y", "-i", os.path.normpath(inp), "-vn", "-c:a", codec]
        if quality != "copy":
            args.extend(["-b:a", quality + "k"])
        args.append(os.path.normpath(out))

        self._a2aConvertBtn.setEnabled(False)
        self._a2aLastOutputPath = out
        self._a2aProgressBar.setVisible(True)
        self._a2aProgressBar.setRange(0, 0)
        self._a2aProcess.start("ffmpeg", args)

    def _a2aReadProcessOutput(self):
        proc = getattr(self, "_a2aProcess", None)
        if proc and proc == self.sender():
            data = proc.readAllStandardError().data() + proc.readAllStandardOutput().data()
            if data:
                pass

    def _a2aProcessFinished(self, exitCode, exitStatus):
        self._a2aConvertBtn.setEnabled(True)
        self._a2aProgressBar.setRange(PROGRESS_MIN, PROGRESS_MAX)
        self._a2aProgressBar.setValue(PROGRESS_MAX if exitCode == 0 else PROGRESS_MIN)
        if exitCode == 0:
            self._a2aOpenFolderBtn.setEnabled(True)
            QMessageBox.information(self, "Аудио конвертер", "Конвертация завершена.")
        else:
            self._a2aOpenFolderBtn.setEnabled(False)
            try:
                if self._a2aLastOutputPath and os.path.exists(self._a2aLastOutputPath):
                    os.remove(self._a2aLastOutputPath)
            except Exception:
                pass
            QMessageBox.warning(self, "Аудио конвертер", "Ошибка конвертации.")

    def _a2aOpenFolder(self):
        path = getattr(self, "_a2aLastOutputPath", "") or self._a2aOutputEdit.text().strip()
        if not path:
            QMessageBox.warning(self, "Аудио конвертер", "Нет выходного файла.")
            return
        out_dir = os.path.dirname(path)
        if not os.path.isdir(out_dir):
            QMessageBox.warning(self, "Аудио конвертер", "Папка не найдена.")
            return
        self._openFolderOrSelectFile(path)
