"""Конфигурация приложения и предупреждения: загрузка/сохранение app_config, проверка ffmpeg/ffprobe, предупреждения о записи."""

import os
import json
import shutil
import platform
import logging
from PySide6.QtWidgets import QMessageBox

from app.constants import JSON_ENCODING, JSON_INDENT, CONFIG_APP_CONFIG

logger = logging.getLogger(__name__)


class ConfigWarningsMixin:
    """Миксин: загрузка/сохранение вкладки, проверка наличия ffmpeg/ffprobe, предупреждения о правах на запись."""

    def _findTool(self, name):
        if not name:
            return False
        names = [name]
        if platform.system() == "Windows":
            names = [name + ".exe", name]
        for candidate in names:
            if shutil.which(candidate):
                return True
        for candidate in names:
            if os.path.exists(os.path.join(self._appDir, candidate)):
                return True
        return False

    def _checkToolsAvailability(self):
        if not self._ffmpegWarningShown and not self._findTool("ffmpeg"):
            self._ffmpegWarningShown = True
            QMessageBox.critical(
                self,
                "FFmpeg не найден",
                "Не удалось найти ffmpeg. Убедитесь, что ffmpeg.exe лежит рядом с приложением "
                "или доступен через PATH."
            )
        if not self._ffprobeWarningShown and not self._findTool("ffprobe"):
            self._ffprobeWarningShown = True
            QMessageBox.warning(
                self,
                "FFprobe не найден",
                "FFprobe не найден. Прогресс кодирования может быть неточным. "
                "Положите ffprobe.exe рядом с приложением или добавьте его в PATH."
            )

    def _warnIfConfigPathNotWritable(self):
        app_dir = self._appDir
        if not os.access(app_dir, os.W_OK):
            QMessageBox.warning(
                self,
                "Настройки не сохраняются",
                "Приложение хранит настройки рядом с файлом запуска. "
                "Похоже, у этой папки нет прав на запись. "
                "Сохранение пресетов и пользовательских настроек может не работать."
            )
            return
        paths = (self._customOptionsPath, self._savedCommandsPath, self._appConfigPath, self.presetManager.presets_file)
        non_writable = [p for p in paths if os.path.exists(p) and not os.access(p, os.W_OK)]
        if non_writable:
            QMessageBox.warning(
                self,
                "Настройки не сохраняются",
                "Не удаётся записывать файлы настроек рядом с приложением. "
                "Проверьте права на запись в папке установки."
            )

    def _warnConfigWriteFailure(self, file_label):
        if file_label in self._configWriteWarningsShown:
            return
        self._configWriteWarningsShown.add(file_label)
        QMessageBox.warning(
            self,
            "Ошибка сохранения",
            f"Не удалось сохранить {file_label}. Проверьте права на запись в папке приложения."
        )

    def _loadAppConfig(self):
        if not os.path.exists(self._appConfigPath):
            return
        try:
            with open(self._appConfigPath, "r", encoding=JSON_ENCODING) as f:
                data = json.load(f)
            idx = data.get("last_tab_index")
            if isinstance(idx, int) and hasattr(self, "_tabWidget"):
                max_idx = self._tabWidget.count() - 1
                idx = max(0, min(idx, max_idx))
                self._tabWidget.setCurrentIndex(idx)
        except Exception:
            logger.exception("Ошибка загрузки app_config")

    def _saveAppConfig(self):
        if not hasattr(self, "_tabWidget"):
            return
        data = {"last_tab_index": self._tabWidget.currentIndex()}
        try:
            with open(self._appConfigPath, "w", encoding=JSON_ENCODING) as f:
                json.dump(data, f, ensure_ascii=False, indent=JSON_INDENT)
        except Exception:
            logger.exception("Ошибка сохранения app_config")
            self._warnConfigWriteFailure(CONFIG_APP_CONFIG)

    def _warnFfprobeMissing(self):
        if self._ffprobeWarningShown:
            return
        self._ffprobeWarningShown = True
        QMessageBox.warning(
            self,
            "FFprobe не найден",
            "FFprobe не найден. Прогресс кодирования может быть неточным. "
            "Положите ffprobe.exe рядом с приложением или добавьте его в PATH."
        )

    def _stopQueueWithError(self, status_text):
        self.isPaused = False
        self._pauseStopRequested = False
        self.pausedQueueIndex = -1
        self.currentQueueIndex = -1
        if hasattr(self.ui, 'runButton'):
            self.ui.runButton.setText("Запустить кодирование")
            self.ui.runButton.setStyleSheet(getattr(self, '_runButtonStyleStart', self._runButtonStyleStart))
            self.ui.runButton.setEnabled(True)
        if hasattr(self.ui, 'pauseResumeButton'):
            self.ui.pauseResumeButton.setEnabled(False)
            self.ui.pauseResumeButton.setText("Пауза")
        self.updateQueueTable()
        self.updateTotalQueueProgress()
        self.updateStatus(status_text)
