"""Миксин: построение команды FFmpeg, запуск процесса кодирования, прогресс, ETA, пауза/возобновление."""

import os
import platform
import shlex
import re
import json
import time
import logging
import subprocess
from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import QProcess, QTimer

from constants import (
    PROGRESS_MAX, PROGRESS_MIN, PROCESS_NEXT_DELAY_MS,
    ETA_DELAY_SECONDS, ETA_SMOOTHING_ALPHA,
)
from queueitem import QueueItem

logger = logging.getLogger(__name__)


class EncodingMixin:
    """Миксин: generateFFmpegCommand, _getFFmpegArgs, процесс очереди, readProcessOutput, processFinished, ETA, пауза."""

    def _quotePath(self, path):
        """Оборачивает путь в кавычки для безопасности."""
        if not path:
            return '""'
        if path.startswith('"') and path.endswith('"'):
            return path
        return f'"{path}"'

    def generateFFmpegCommand(self):
        """Генерирует команду FFmpeg для выделенного файла (строка для отображения)."""
        item = self.getSelectedQueueItem()
        if not item:
            return "ffmpeg"
        input_file = item.file_path
        input_file_normalized = os.path.normpath(input_file)
        container = item.container or "current"
        if container in ("default", "current", "", None):
            container_ext = os.path.splitext(input_file_normalized)[1].lstrip(".")
        else:
            container_ext = container
        if item.output_file:
            output_base = os.path.splitext(item.output_file)[0]
            final_output = output_base + "." + container_ext
            final_output = os.path.normpath(final_output)
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
            input_path = os.path.dirname(input_file_normalized)
            input_base = os.path.splitext(os.path.basename(input_file_normalized))[0]
            base_output = os.path.join(input_path, input_base + "_converted")
            output_file = base_output + "." + container_ext
            counter = 1
            final_output = output_file
            while os.path.exists(final_output):
                final_output = base_output + "_" + str(counter) + "." + container_ext
                counter += 1
            final_output = os.path.normpath(final_output)
            item.output_file = final_output
            item.output_renamed = False
        self.lastOutputFile = final_output
        codec = item.codec or "current"
        codec_args = []
        if codec not in ("default", "current", ""):
            codec_args = ["-c:v", codec]
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
        if getattr(item, "vf_lanczos", False):
            if scale:
                if "flags=" not in scale:
                    scale = scale + ":flags=lanczos"
            else:
                scale = "scale=iw:ih:flags=lanczos"
        vf_args = []
        if scale and codec != "copy":
            vf_args = ["-vf", scale]
        video_extra = []
        if codec != "copy":
            if getattr(item, "crf", 0) > 0:
                video_extra += ["-crf", str(item.crf)]
            if getattr(item, "bitrate", 0) > 0:
                video_extra += ["-b:v", str(item.bitrate) + "k"]
            if getattr(item, "fps", 0) > 0:
                video_extra += ["-r", str(item.fps)]
            if codec in ("libx264", "libx265", "current", "default", "") and getattr(item, "preset_speed", ""):
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
        container_ext_l = container_ext.lower() if isinstance(container_ext, str) else ""
        apply_tag_hvc1 = tag_hvc1 and container_ext_l in ("mp4", "mov", "m4v") and (
            codec in ("libx265", "hevc", "h265", "copy")
        )
        segments = self._getTrimSegments(item)
        extra_args = self._getExtraArgsList(getattr(item, "extra_args", ""))
        extra_args = self._filterExtraArgsList(extra_args, item)
        cmd_parts = ["ffmpeg"]
        if len(segments) == 1:
            start_sec, end_sec = segments[0]
            cmd_parts += ["-ss", str(start_sec), "-i", self._quotePath(input_file_normalized), "-to", str(end_sec)]
            cmd_parts += vf_args + codec_args + video_extra + audio_args
            if apply_tag_hvc1:
                cmd_parts += ["-tag:v", "hvc1"]
            if extra_args:
                cmd_parts += extra_args
        elif len(segments) > 1:
            include_audio = getattr(item, "has_audio", None) is not False
            filter_complex, map_v, map_a = self._buildTrimConcatFilter(segments, scale, include_audio=include_audio)
            codec_display = codec if codec not in ("default", "current", "") else "libx264"
            cmd_parts += ["-i", self._quotePath(input_file_normalized), "-filter_complex", f'"{filter_complex}"', "-map", map_v, "-c:v", codec_display]
            cmd_parts += video_extra
            if include_audio and map_a:
                audio_for_filter = ["-c:a", "aac"]
                if getattr(item, "audio_bitrate", 0) > 0:
                    audio_for_filter += ["-b:a", str(item.audio_bitrate) + "k"]
                if getattr(item, "sample_rate", 0) > 0:
                    audio_for_filter += ["-ar", str(item.sample_rate)]
                cmd_parts += ["-map", map_a]
                cmd_parts += audio_for_filter
            if apply_tag_hvc1:
                cmd_parts += ["-tag:v", "hvc1"]
            if extra_args:
                cmd_parts += extra_args
        else:
            cmd_parts += ["-i", self._quotePath(input_file_normalized)]
            cmd_parts += vf_args + codec_args + video_extra + audio_args
            if apply_tag_hvc1:
                cmd_parts += ["-tag:v", "hvc1"]
            if extra_args:
                cmd_parts += extra_args
        cmd_parts.append(self._quotePath(final_output))
        return " ".join(cmd_parts)

    def _generateOutputFileForItem(self, queue_item):
        """Генерирует выходной файл для элемента очереди."""
        if not queue_item or queue_item.output_file:
            return
        input_file = queue_item.file_path
        input_file_normalized = os.path.normpath(input_file)
        container = queue_item.container or "current"
        if container in ("default", "current", "", None):
            container_ext = os.path.splitext(input_file_normalized)[1].lstrip(".")
        else:
            container_ext = container
        input_path = os.path.dirname(input_file_normalized)
        input_base = os.path.splitext(os.path.basename(input_file_normalized))[0]
        base_output = os.path.join(input_path, input_base + "_converted")
        output_file = base_output + "." + container_ext
        counter = 1
        final_output = output_file
        while os.path.exists(final_output):
            final_output = base_output + "_" + str(counter) + "." + container_ext
            counter += 1
        final_output = os.path.normpath(final_output)
        queue_item.output_file = final_output
        queue_item.output_chosen_by_user = False

    def _getTrimSegments(self, queue_item):
        """Возвращает список областей обрезки (start_sec, end_sec)."""
        out = list(getattr(queue_item, "keep_segments", []) or [])
        start = getattr(queue_item, "trim_start_sec", None)
        end = getattr(queue_item, "trim_end_sec", None)
        if start is not None and end is not None and end > start:
            out.append((start, end))
        return out

    def _buildTrimConcatFilter(self, segments, scale_filter, include_audio=True):
        """Строит filter_complex для обрезки/склейки. Возвращает (filter_string, map_v, map_a)."""
        parts = []
        for i, (s, e) in enumerate(segments):
            if include_audio:
                parts.append(
                    f"[0:v]trim=start={s}:end={e},setpts=PTS-STARTPTS[v{i}];"
                    f"[0:a]atrim=start={s}:end={e},asetpts=PTS-STARTPTS[a{i}]"
                )
            else:
                parts.append(f"[0:v]trim=start={s}:end={e},setpts=PTS-STARTPTS[v{i}]")
        n = len(segments)
        if include_audio:
            concat_inputs = "".join(f"[v{i}][a{i}]" for i in range(n))
            parts.append(f"{concat_inputs}concat=n={n}:v=1:a=1[outv][outa]")
            map_a = "[outa]"
        else:
            concat_inputs = "".join(f"[v{i}]" for i in range(n))
            parts.append(f"{concat_inputs}concat=n={n}:v=1:a=0[outv]")
            map_a = None
        map_v = "[outv]"
        if scale_filter:
            parts.append(f"[outv]{scale_filter}[v]")
            map_v = "[v]"
        return ";".join(parts), map_v, map_a

    def _getFFmpegArgs(self, queue_item=None):
        """Возвращает список аргументов для запуска FFmpeg (без кавычек вокруг путей)."""
        if queue_item is None:
            queue_item = self.getSelectedQueueItem()
        if not queue_item:
            return []
        input_file = queue_item.file_path
        input_file_normalized = os.path.normpath(input_file)
        container = queue_item.container or "current"
        if container in ("default", "current", "", None):
            container_ext = os.path.splitext(input_file_normalized)[1].lstrip(".")
        else:
            container_ext = container
        if queue_item.output_file:
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
            input_path = os.path.dirname(input_file_normalized)
            input_base = os.path.splitext(os.path.basename(input_file_normalized))[0]
            base_output = os.path.join(input_path, input_base + "_converted")
            output_file = base_output + "." + container_ext
            counter = 1
            final_output = output_file
            while os.path.exists(final_output):
                final_output = base_output + "_" + str(counter) + "." + container_ext
                counter += 1
            final_output = os.path.normpath(final_output)
            queue_item.output_file = final_output
            queue_item.output_renamed = False
        self.lastOutputFile = final_output
        codec = queue_item.codec or "current"
        codec_args = []
        if codec not in ("default", "current", ""):
            codec_args = ["-c:v", codec]
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
        if getattr(queue_item, "vf_lanczos", False):
            if scale:
                if "flags=" not in scale:
                    scale = scale + ":flags=lanczos"
            else:
                scale = "scale=iw:ih:flags=lanczos"
        vf_args = []
        if scale and codec != "copy":
            vf_args = ["-vf", scale]
        video_extra = []
        if codec != "copy":
            if getattr(queue_item, "crf", 0) > 0:
                video_extra += ["-crf", str(queue_item.crf)]
            if getattr(queue_item, "bitrate", 0) > 0:
                video_extra += ["-b:v", str(queue_item.bitrate) + "k"]
            if getattr(queue_item, "fps", 0) > 0:
                video_extra += ["-r", str(queue_item.fps)]
            if codec in ("libx264", "libx265", "current", "default", "") and getattr(queue_item, "preset_speed", ""):
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
        container_ext_l = container_ext.lower() if isinstance(container_ext, str) else ""
        apply_tag_hvc1 = tag_hvc1 and container_ext_l in ("mp4", "mov", "m4v") and (
            codec in ("libx265", "hevc", "h265", "copy")
        )
        extra_args = self._getExtraArgsList(getattr(queue_item, "extra_args", ""))
        extra_args = self._filterExtraArgsList(extra_args, queue_item)
        segments = self._getTrimSegments(queue_item)
        probe_args = ["-analyzeduration", "10000000", "-probesize", "10000000"] if segments else []
        if len(segments) == 1:
            start_sec, end_sec = segments[0]
            args = probe_args + ["-ss", str(start_sec), "-i", input_file_normalized, "-to", str(end_sec)]
            args += vf_args + codec_args + video_extra + audio_args
            if apply_tag_hvc1:
                args += ["-tag:v", "hvc1"]
            if extra_args:
                args += extra_args
            args.append(final_output)
        elif len(segments) > 1:
            include_audio = getattr(queue_item, "has_audio", None) is not False
            filter_complex, map_v, map_a = self._buildTrimConcatFilter(segments, scale, include_audio=include_audio)
            codec_val = (queue_item.codec or "libx264") if (queue_item.codec and queue_item.codec not in ("default", "current", "")) else "libx264"
            args = probe_args + ["-i", input_file_normalized, "-filter_complex", filter_complex, "-map", map_v, "-c:v", codec_val]
            args += video_extra
            if include_audio and map_a:
                audio_args_filter = ["-c:a", "aac"]
                if getattr(queue_item, "audio_bitrate", 0) > 0:
                    audio_args_filter += ["-b:a", str(queue_item.audio_bitrate) + "k"]
                if getattr(queue_item, "sample_rate", 0) > 0:
                    audio_args_filter += ["-ar", str(queue_item.sample_rate)]
                args += ["-map", map_a]
                args += audio_args_filter
            if apply_tag_hvc1:
                args += ["-tag:v", "hvc1"]
            if extra_args:
                args += extra_args
            args.append(final_output)
        else:
            args = ["-i", input_file_normalized]
            args += vf_args + codec_args + video_extra + audio_args
            if apply_tag_hvc1:
                args += ["-tag:v", "hvc1"]
            if extra_args:
                args += extra_args
            args.append(final_output)
        if getattr(queue_item, "output_chosen_by_user", False):
            args = ["-y"] + args
        return args

    def onRunButtonClicked(self):
        if self.currentQueueIndex >= 0:
            reply = QMessageBox.question(
                self, "Завершить кодирование?", "Вы уверены, что хотите завершить кодирование?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
            self._abortRequested = True
            if self.ffmpegProcess.state() == QProcess.Running:
                self.ffmpegProcess.kill()
            else:
                self._applyAbortReset()
            return
        self.startQueueProcessing()

    def _applyAbortReset(self):
        self._abortRequested = False
        if self.currentQueueIndex >= 0 and self.currentQueueIndex < len(self.queue):
            item = self.queue[self.currentQueueIndex]
            try:
                if item.output_file and os.path.exists(item.output_file):
                    os.remove(item.output_file)
            except Exception:
                pass
        for it in self.queue:
            it.status = QueueItem.STATUS_WAITING
            it.progress = 0
            it.error_message = ""
        self.currentQueueIndex = -1
        self.isPaused = False
        self._pauseStopRequested = False
        self.pausedQueueIndex = -1
        if hasattr(self.ui, 'runButton'):
            self.ui.runButton.setText("Запустить кодирование")
            self.ui.runButton.setStyleSheet(getattr(self, '_runButtonStyleStart', self._runButtonStyleStart))
            self.ui.runButton.setEnabled(True)
        if hasattr(self.ui, 'pauseResumeButton'):
            self.ui.pauseResumeButton.setEnabled(False)
            self.ui.pauseResumeButton.setText("Пауза")
        self.updateQueueTable()
        self.updateTotalQueueProgress()
        self.updateStatus("Кодирование прервано. Можно удалять файлы из очереди.")

    def startQueueProcessing(self):
        if not self.queue:
            QMessageBox.information(self, "Очередь", "Очередь пуста. Добавьте файлы для обработки.")
            return
        if self.ffmpegProcess.state() != QProcess.NotRunning:
            QMessageBox.information(self, "Ожидание", "Дождитесь завершения текущего кодирования")
            return
        for it in self.queue:
            it.status = QueueItem.STATUS_WAITING
            it.progress = 0
            it.error_message = ""
            it.output_renamed = False
            it.encoding_duration = 0
            it.processed_frames = 0
        self._queueProgressMaxValue = 0
        self._queueProgressTarget = 0
        if hasattr(self.ui, 'totalQueueProgressBar'):
            self.ui.totalQueueProgressBar.setValue(0)
        for it in self.queue:
            self._getVideoDurationForItem(it)
        self.updateQueueTable()
        self.updateTotalQueueProgress()
        self.isPaused = False
        self._pauseStopRequested = False
        self.pausedQueueIndex = -1
        self.currentQueueIndex = 0
        self.processNextInQueue()

    def processNextInQueue(self):
        if self.currentQueueIndex < 0 or self.currentQueueIndex >= len(self.queue):
            self.currentQueueIndex = -1
            if hasattr(self.ui, 'runButton'):
                self.ui.runButton.setText("Запустить кодирование")
                self.ui.runButton.setStyleSheet(getattr(self, '_runButtonStyleStart', self._runButtonStyleStart))
                self.ui.runButton.setEnabled(True)
            self.updateStatus("Все файлы обработаны")
            QMessageBox.information(self, "Готово", "Обработка всех файлов завершена!")
            return
        item = self.queue[self.currentQueueIndex]
        item.status = QueueItem.STATUS_PROCESSING
        item.progress = 0
        self.updateQueueTable()
        self.updateStatus(f"Обработка файла {self.currentQueueIndex + 1} из {len(self.queue)}")
        if getattr(item, "command_manually_edited", False) and getattr(item, "command", "").strip():
            try:
                cmd_from_item = item.command.strip()
                args = self._parseCommand(cmd_from_item)
                args = self._substitutePathsInArgs(args, item)
            except Exception as e:
                QMessageBox.warning(
                    self, "Предупреждение",
                    f"Ошибка парсинга отредактированной команды для файла:\n{item.file_path}\n\n{str(e)}\n\n"
                    "Будет использована автоматически сгенерированная команда."
                )
                args = self._getFFmpegArgs(item)
        else:
            args = self._getFFmpegArgs(item)
        if not args:
            QMessageBox.warning(self, "Ошибка", f"Не удалось сгенерировать команду для файла:\n{item.file_path}")
            item.status = QueueItem.STATUS_ERROR
            item.error_message = "Ошибка генерации команды"
            self.currentQueueIndex += 1
            self.processNextInQueue()
            return
        self.updateQueueTable()
        if not os.path.exists(item.file_path):
            QMessageBox.critical(self, "Ошибка", f"Файл не существует:\n{item.file_path}")
            item.status = QueueItem.STATUS_ERROR
            item.error_message = "Файл не существует"
            self.currentQueueIndex += 1
            self.processNextInQueue()
            return
        self.ui.logDisplay.append(f"<br><b>=== Обработка файла {self.currentQueueIndex + 1}: {os.path.basename(item.file_path)} ===</b><br>")
        if hasattr(self.ui, 'runButton'):
            self.ui.runButton.setText("Завершить кодирование")
            self.ui.runButton.setStyleSheet(getattr(self, '_runButtonStyleAbort', self._runButtonStyleAbort))
            self.ui.runButton.setEnabled(True)
        if hasattr(self.ui, 'pauseResumeButton'):
            self.ui.pauseResumeButton.setEnabled(True)
            self.ui.pauseResumeButton.setText("Пауза")
        self.encodingDuration = 0
        self.currentFrame = 0
        item.processed_frames = 0
        self._resetEtaTracking()
        if hasattr(self.ui, 'encodingProgressBar'):
            self.ui.encodingProgressBar.setValue(0)
        self._getVideoDurationForItem(item)
        self._warnConcatAudioBehavior(item)
        self.ffmpegProcess.start("ffmpeg", args)

    def _splitArgs(self, value):
        if not value:
            return []
        posix = platform.system() != "Windows"
        try:
            return shlex.split(value, posix=posix)
        except ValueError:
            return value.split()

    def _parseCommand(self, cmd_string):
        parts = self._splitArgs(cmd_string)
        if parts and parts[0].lower() == "ffmpeg":
            parts = parts[1:]
        return parts

    def _argsToCommand(self, args):
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

    def onProcessError(self, error):
        if getattr(self, '_closingApp', False):
            return
        error_map = {
            QProcess.ProcessError.FailedToStart: "Не удалось запустить FFmpeg. Проверьте, что ffmpeg доступен.",
            QProcess.ProcessError.Crashed: "Процесс FFmpeg завершился аварийно.",
            QProcess.ProcessError.Timedout: "FFmpeg не отвечает (таймаут).",
            QProcess.ProcessError.WriteError: "Ошибка записи в процесс FFmpeg.",
            QProcess.ProcessError.ReadError: "Ошибка чтения из процесса FFmpeg.",
            QProcess.ProcessError.UnknownError: "Неизвестная ошибка процесса FFmpeg.",
        }
        message = error_map.get(error, "Ошибка процесса FFmpeg.")
        if error == QProcess.ProcessError.FailedToStart:
            self._ffmpegWarningShown = True
        item = None
        if 0 <= self.currentQueueIndex < len(self.queue):
            item = self.queue[self.currentQueueIndex]
        if item:
            item.status = QueueItem.STATUS_ERROR
            item.error_message = message
        if hasattr(self.ui, "logDisplay"):
            self.ui.logDisplay.append(f"<br><b><font color='red'>✗ {message}</font></b>")
        QMessageBox.critical(self, "Ошибка FFmpeg", message)
        self._stopQueueWithError("Ошибка кодирования. Проверьте FFmpeg.")

    def _warnConcatAudioBehavior(self, item):
        if not item:
            return
        segments = self._getTrimSegments(item)
        if len(segments) <= 1:
            return
        has_audio = getattr(item, "has_audio", None)
        if has_audio is False and not getattr(item, "no_audio_warning_shown", False):
            item.no_audio_warning_shown = True
            QMessageBox.warning(
                self, "Склейка без аудио",
                "В выбранном файле нет аудиодорожки. При склейке сегментов звук отсутствует."
            )
        if has_audio is not False and not getattr(item, "concat_audio_warning_shown", False):
            item.concat_audio_warning_shown = True
            QMessageBox.information(
                self, "Склейка сегментов",
                "При склейке нескольких сегментов звук перекодируется в AAC, выбор аудиокодека игнорируется."
            )

    def _applyPathsToSavedCommand(self, item, update_display=False):
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
        return self._splitArgs(extra_args_str)

    def _filterExtraArgsList(self, args, queue_item):
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
            if input_path and os.path.normpath(token) == input_path:
                i += 1
                continue
            if output_path and os.path.normpath(token) == output_path:
                i += 1
                continue
            if not token.startswith("-") and "=" not in token:
                if any(sep in token for sep in ("/", "\\")) or (":" in token and len(token) > 2):
                    i += 1
                    continue
            out.append(token)
            i += 1
        return out

    def _stripInputOutputArgs(self, args):
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
        base = list(base_pairs)
        extra = []
        for pair in user_pairs:
            if pair in base:
                base.remove(pair)
            else:
                extra.append(pair)
        return extra

    def _extractExtraArgsFromCommands(self, base_cmd, user_cmd):
        base_args = self._stripInputOutputArgs(self._parseCommand(base_cmd))
        user_args = self._stripInputOutputArgs(self._parseCommand(user_cmd))
        base_pairs = self._tokenizeArgsPairs(base_args)
        user_pairs = self._tokenizeArgsPairs(user_args)
        extra_pairs = self._diffArgsPairs(base_pairs, user_pairs)
        extra = []
        for flag, val in extra_pairs:
            extra.append(flag)
            if val is not None:
                extra.append(val)
        return extra

    def _substitutePathsInArgs(self, args, queue_item):
        if not args or not queue_item:
            return args
        args = list(args)
        input_path = os.path.normpath(queue_item.file_path)
        if not queue_item.output_file:
            self._generateOutputFileForItem(queue_item)
        output_path = os.path.normpath(queue_item.output_file) if queue_item.output_file else ""
        for i in range(len(args) - 1):
            if args[i] == "-i":
                args[i + 1] = input_path
                break
        if output_path and len(args) >= 1:
            args[-1] = output_path
        return args

    def readProcessOutput(self):
        out = self.ffmpegProcess.readAllStandardOutput().data().decode('utf-8', errors='replace').strip()
        err = self.ffmpegProcess.readAllStandardError().data().decode('utf-8', errors='replace').strip()
        if out:
            self._appendLog(out, 'info')
            self._parseProgressFromLog(out)
        if err:
            self._appendLog(err, 'error')
            self._parseProgressFromLog(err)

    def _appendLog(self, text, source='info'):
        if not text:
            return
        for line in text.split('\n'):
            line = line.strip()
            if not line:
                continue
            color = self._determineLogColor(line, source)
            self.ui.logDisplay.append(f"<font color='{color}'>{line}</font>")

    def _determineLogColor(self, line, source):
        line_lower = line.lower()
        if any(k in line_lower for k in ['error', 'failed', 'cannot', 'invalid', 'unable', 'not found']):
            return 'red'
        if any(k in line_lower for k in ['warning', 'deprecated']):
            return '#FF8C00'
        if any(k in line_lower for k in ['success', 'complete', 'done', 'finished']):
            return 'green'
        if any(k in line_lower for k in ['frame=', 'fps=', 'bitrate=', 'time=', 'size=']):
            return '#0066CC'
        if source == 'error':
            if any(k in line_lower for k in ['stream', 'video:', 'audio:', 'duration:', 'input', 'output']):
                return 'black'
            if not any(k in line_lower for k in ['error', 'failed']):
                return '#666666'
        return 'black' if source == 'info' else '#666666'

    def _parseProgressFromLog(self, line):
        if self.currentQueueIndex < 0 or self.currentQueueIndex >= len(self.queue):
            return
        item = self.queue[self.currentQueueIndex]
        frame_match = re.search(r'frame=\s*(\d+)', line)
        if frame_match:
            self.currentFrame = int(frame_match.group(1))
            try:
                prev = getattr(item, "processed_frames", 0) or 0
                item.processed_frames = max(prev, self.currentFrame)
            except Exception:
                item.processed_frames = self.currentFrame
        time_match = re.search(r'time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})', line)
        if time_match:
            hours, minutes, seconds, centiseconds = int(time_match.group(1)), int(time_match.group(2)), int(time_match.group(3)), int(time_match.group(4))
            self.encodingDuration = hours * 3600 + minutes * 60 + seconds + centiseconds / 100.0
            item.encoding_duration = self.encodingDuration
            if self._etaStartTs is None:
                self._etaStartTs = time.monotonic()
        self._updateSpeedFromLog(line)
        self.updateEncodingProgress()

    def updateEncodingProgress(self):
        if self.currentQueueIndex < 0 or self.currentQueueIndex >= len(self.queue):
            return
        item = self.queue[self.currentQueueIndex]
        if item.video_duration > 0 and self.encodingDuration > 0:
            progress = min(PROGRESS_MAX, int((self.encodingDuration / item.video_duration) * PROGRESS_MAX))
            self.encodingProgress = progress
            item.progress = progress
            if hasattr(self.ui, 'encodingProgressBar'):
                self.ui.encodingProgressBar.setValue(progress)
            if hasattr(self.ui, 'queueTableWidget'):
                table = self.ui.queueTableWidget
                if self.currentQueueIndex < table.rowCount():
                    progress_item = table.item(self.currentQueueIndex, 4)
                    if progress_item:
                        progress_item.setText(f"{progress}%")
            if hasattr(self.ui, 'videoTimelineSlider') and item.video_duration > 0:
                if not self.ui.videoTimelineSlider.isSliderDown():
                    max_value = self.ui.videoTimelineSlider.maximum()
                    timeline_position = int((self.encodingDuration / item.video_duration) * max_value)
                    self.ui.videoTimelineSlider.setValue(timeline_position)
            if item.status == QueueItem.STATUS_PROCESSING:
                now = time.monotonic()
                eta_ready = (
                    self._etaStartTs is not None
                    and (now - self._etaStartTs) >= self._etaDelaySeconds
                    and self._emaSpeed is not None
                    and self._emaSpeed > 0.01
                )
                if eta_ready:
                    remaining = max(0.0, item.video_duration - self.encodingDuration)
                    eta_seconds = remaining / self._emaSpeed
                    eta_text = self._formatTime(eta_seconds)
                    queue_eta_text = None
                    if all(getattr(it, "video_duration", 0) > 0 for it in self.queue):
                        remaining_queue = sum(
                            getattr(it, "video_duration", 0) or 0
                            for it in self.queue[self.currentQueueIndex + 1:]
                        )
                        remaining_queue += remaining
                        queue_eta_seconds = remaining_queue / self._emaSpeed
                        queue_eta_text = self._formatTime(queue_eta_seconds)
                    base = f"Обработка файла {self.currentQueueIndex + 1} из {len(self.queue)}"
                    if queue_eta_text:
                        self.updateStatus(f"{base} — осталось: {eta_text}, очередь: {queue_eta_text}")
                    else:
                        self.updateStatus(f"{base} — осталось: {eta_text}")
        self.updateTotalQueueProgress()

    def updateTotalQueueProgress(self):
        if not self.queue or not hasattr(self.ui, 'totalQueueProgressBar'):
            return
        have_frames = all(getattr(it, "total_frames", 0) > 0 for it in self.queue)
        total_frames = sum(getattr(it, "total_frames", 0) or 0 for it in self.queue) if have_frames else 0
        if total_frames > 0:
            done_frames = sum(getattr(it, "total_frames", 0) or 0 for it in self.queue if it.status == QueueItem.STATUS_SUCCESS)
            if self.currentQueueIndex >= 0 and self.currentQueueIndex < len(self.queue):
                current_item = self.queue[self.currentQueueIndex]
                if current_item.status == QueueItem.STATUS_PROCESSING:
                    cur_total = getattr(current_item, "total_frames", 0) or 0
                    cur_done = getattr(current_item, "processed_frames", 0) or 0
                    if cur_total > 0:
                        done_frames += min(cur_done, cur_total)
            percentage = int(min(float(PROGRESS_MAX), (done_frames / total_frames) * PROGRESS_MAX))
            self._setQueueProgressTarget(percentage)
            return
        total_duration = sum(max(0.0, getattr(it, "video_duration", 0) or 0) for it in self.queue)
        if total_duration > 0:
            done = sum(max(0.0, getattr(it, "video_duration", 0) or 0) for it in self.queue if it.status == QueueItem.STATUS_SUCCESS)
            if self.currentQueueIndex >= 0 and self.currentQueueIndex < len(self.queue):
                current_item = self.queue[self.currentQueueIndex]
                if current_item.status == QueueItem.STATUS_PROCESSING:
                    cur_dur = max(0.0, getattr(current_item, "video_duration", 0) or 0)
                    cur_time = max(0.0, getattr(current_item, "encoding_duration", 0) or 0)
                    if cur_dur > 0:
                        done += min(cur_time, cur_dur)
            percentage = int(min(float(PROGRESS_MAX), (done / total_duration) * PROGRESS_MAX))
            self._setQueueProgressTarget(percentage)
            return
        total_files = len(self.queue)
        completed_files = sum(1 for item in self.queue if item.status == QueueItem.STATUS_SUCCESS)
        current_progress = 0
        if self.currentQueueIndex >= 0 and self.currentQueueIndex < len(self.queue):
            current_item = self.queue[self.currentQueueIndex]
            if current_item.status == QueueItem.STATUS_PROCESSING:
                current_progress = current_item.progress
        total_progress = completed_files * 100 + current_progress
        max_progress = total_files * 100
        self._setQueueProgressTarget(int(total_progress / max_progress * PROGRESS_MAX) if max_progress > 0 else 0)

    def _setQueueProgressTarget(self, value):
        if not hasattr(self.ui, 'totalQueueProgressBar'):
            return
        value = max(PROGRESS_MIN, min(PROGRESS_MAX, int(value)))
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
        current = min(target, current + step) if current < target else max(target, current - step)
        self.ui.totalQueueProgressBar.setValue(current)

    def _resetEtaTracking(self):
        self._etaStartTs = None
        self._emaSpeed = None
        self._speedSampleCount = 0

    def _updateSpeedFromLog(self, line):
        speed_match = re.search(r'speed=\s*([0-9]*\.?[0-9]+)x', line)
        if not speed_match:
            return
        try:
            speed = float(speed_match.group(1))
        except ValueError:
            return
        if speed <= 0:
            return
        if self._etaStartTs is None:
            self._etaStartTs = time.monotonic()
        if self._emaSpeed is None:
            self._emaSpeed = speed
            self._speedSampleCount = 1
            return
        alpha = self._etaSmoothingAlpha
        self._emaSpeed = alpha * speed + (1 - alpha) * self._emaSpeed
        self._speedSampleCount += 1

    def togglePauseEncoding(self):
        if self.isPaused:
            self.resumeEncoding()
            return
        if not self.ffmpegProcess or self.ffmpegProcess.state() == QProcess.NotRunning:
            return
        self.pauseEncoding()

    def pauseEncoding(self):
        if self.ffmpegProcess.state() != QProcess.Running:
            return
        if self.currentQueueIndex < 0 or self.currentQueueIndex >= len(self.queue):
            return
        item = self.queue[self.currentQueueIndex]
        self.isPaused = True
        self._pauseStopRequested = True
        self.pausedQueueIndex = self.currentQueueIndex
        for i in range(self.currentQueueIndex, len(self.queue)):
            self.queue[i].status = QueueItem.STATUS_WAITING
            self.queue[i].progress = 0
            self.queue[i].error_message = ""
        try:
            if platform.system() == "Windows":
                self.ffmpegProcess.kill()
            else:
                import signal
                try:
                    os.kill(self.ffmpegProcess.processId(), signal.SIGSTOP)
                except (ProcessLookupError, PermissionError) as e:
                    QMessageBox.warning(self, "Ошибка", f"Не удалось приостановить процесс: {str(e)}")
                    self.isPaused = False
                    item.status = QueueItem.STATUS_PROCESSING
                    return
        except Exception as e:
            QMessageBox.warning(self, "Предупреждение", f"Ошибка при паузе: {str(e)}")
            self.isPaused = False
            item.status = QueueItem.STATUS_PROCESSING
            return
        self.updateQueueTable()
        self.updateTotalQueueProgress()
        if hasattr(self.ui, 'pauseResumeButton'):
            self.ui.pauseResumeButton.setText("Возобновить")
        self.updateStatus("Остановлено. Нажмите ▶ Возобновить для продолжения.")

    def resumeEncoding(self):
        if not self.isPaused:
            return
        if self.pausedQueueIndex < 0 or self.pausedQueueIndex >= len(self.queue):
            QMessageBox.warning(self, "Ошибка", "Не удалось определить файл для возобновления")
            self.isPaused = False
            self._pauseStopRequested = False
            return
        item = self.queue[self.pausedQueueIndex]
        if item.output_file and os.path.exists(item.output_file):
            try:
                os.remove(item.output_file)
            except Exception:
                pass
        self.isPaused = False
        self._pauseStopRequested = False
        self.currentQueueIndex = self.pausedQueueIndex
        if hasattr(self.ui, 'pauseResumeButton'):
            self.ui.pauseResumeButton.setText("Пауза")
        self.processNextInQueue()

    def _getVideoDurationForItem(self, item):
        if not item or not item.file_path:
            return
        try:
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
                pass
            cmd = [
                ffprobe_executable, '-v', 'error',
                '-show_entries', 'format=duration:stream=codec_type,avg_frame_rate,nb_frames',
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
                streams = data.get("streams") or []
                if streams:
                    item.has_audio = any(s.get("codec_type") == "audio" for s in streams)
                    stream = next((s for s in streams if s.get("codec_type") == "video"), {}) or {}
                    fps_str = stream.get("avg_frame_rate", "") or ""
                    nb_frames_str = stream.get("nb_frames", "") or ""
                    fps_val = 0.0
                    if fps_str and fps_str != "0/0":
                        if "/" in fps_str:
                            num, den = fps_str.split("/", 1)
                            try:
                                fps_val = float(num) / float(den) if float(den) else 0.0
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
                else:
                    item.has_audio = None
        except FileNotFoundError:
            logger.warning("Не удалось получить длительность видео: ffprobe не найден.")
            self._warnFfprobeMissing()
        except Exception:
            logger.exception("Не удалось получить длительность видео")

    def processFinished(self, exitCode, exitStatus):
        if getattr(self, '_closingApp', False):
            return
        if self.currentQueueIndex < 0 or self.currentQueueIndex >= len(self.queue):
            return
        if getattr(self, '_abortRequested', False):
            self._applyAbortReset()
            return
        item = self.queue[self.currentQueueIndex]
        if self.isPaused and self._pauseStopRequested:
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
        if exitCode == 0:
            item.status = QueueItem.STATUS_SUCCESS
            item.progress = PROGRESS_MAX
            if getattr(item, "total_frames", 0):
                item.processed_frames = item.total_frames
            self.ui.logDisplay.append(f"<br><b><font color='green'>✓ Файл обработан успешно: {os.path.basename(item.file_path)}</font></b>")
        else:
            item.status = QueueItem.STATUS_ERROR
            item.error_message = f"Код завершения: {exitCode}"
            self.ui.logDisplay.append(f"<br><b><font color='red'>✗ Ошибка обработки файла: {os.path.basename(item.file_path)} (код: {exitCode})</font></b>")
            try:
                if item.output_file and os.path.exists(item.output_file):
                    os.remove(item.output_file)
            except Exception:
                pass
        self.updateQueueTable()
        self.updateTotalQueueProgress()
        if hasattr(self.ui, 'encodingProgressBar'):
            self.ui.encodingProgressBar.setValue(PROGRESS_MAX if exitCode == 0 else PROGRESS_MIN)
        if hasattr(self.ui, 'pauseResumeButton'):
            self.ui.pauseResumeButton.setEnabled(False)
            self.ui.pauseResumeButton.setText("Пауза")
        self.isPaused = False
        self.currentQueueIndex += 1
        if self.currentQueueIndex < len(self.queue):
            QTimer.singleShot(PROCESS_NEXT_DELAY_MS, self.processNextInQueue)
        else:
            self.currentQueueIndex = -1
            if hasattr(self.ui, 'runButton'):
                self.ui.runButton.setText("Запустить кодирование")
                self.ui.runButton.setStyleSheet(getattr(self, '_runButtonStyleStart', self._runButtonStyleStart))
                self.ui.runButton.setEnabled(True)
            self.updateStatus("Все файлы обработаны")
            if hasattr(self.ui, 'openOutputFolderButton'):
                self.ui.openOutputFolderButton.setEnabled(True)
