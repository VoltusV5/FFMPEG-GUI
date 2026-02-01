"""Элемент очереди кодирования."""


class QueueItem:
    STATUS_WAITING = "waiting"
    STATUS_PROCESSING = "processing"
    STATUS_SUCCESS = "success"
    STATUS_ERROR = "error"
    STATUS_PAUSED = "paused"

    STATUS_LABELS = {
        STATUS_WAITING: "⏳ Ожидание",
        STATUS_PROCESSING: "🔄 В процессе",
        STATUS_SUCCESS: "✅ Успех",
        STATUS_ERROR: "❌ Ошибка",
        STATUS_PAUSED: "⏸ Приостановлено",
    }

    def __init__(self, file_path):
        self.file_path = file_path
        self.preset_name = "default"
        self.status = QueueItem.STATUS_WAITING
        self.progress = 0
        self.output_file = ""
        self.error_message = ""
        self.output_renamed = False
        self.output_chosen_by_user = False

        self.keep_segments = []
        self.trim_start_sec = None
        self.trim_end_sec = None

        self.codec = "default"
        self.container = "default"
        self.resolution = "default"
        self.custom_resolution = ""
        self.audio_codec = "current"

        self.crf = 0
        self.bitrate = 0
        self.fps = 0
        self.audio_bitrate = 0
        self.sample_rate = 0
        self.preset_speed = "medium"
        self.profile_level = ""
        self.pixel_format = ""
        self.tune = ""
        self.threads = 0
        self.keyint = 0
        self.tag_hvc1 = False
        self.vf_lanczos = False
        self.extra_args = ""

        self.encoding_duration = 0
        self.video_duration = 0
        self.video_fps = 0
        self.total_frames = 0
        self.processed_frames = 0
        self.has_audio = None
        self.no_audio_warning_shown = False
        self.concat_audio_warning_shown = False

        self.command = ""
        self.command_manually_edited = False
        self.last_generated_command = ""

    def setPreset(self, preset_data):
        """Устанавливает параметры из пресета"""
        if preset_data:
            self.codec = preset_data.get('codec', 'default')
            self.container = preset_data.get('container', 'default')
            self.resolution = preset_data.get('resolution', 'default')
            self.audio_codec = preset_data.get('audio_codec', 'current')
            self.crf = int(preset_data.get('crf', 0) or 0)
            self.bitrate = int(preset_data.get('bitrate', 0) or 0)
            self.fps = int(preset_data.get('fps', 0) or 0)
            self.audio_bitrate = int(preset_data.get('audio_bitrate', 0) or 0)
            self.sample_rate = int(preset_data.get('sample_rate', 0) or 0)
            self.preset_speed = preset_data.get('preset_speed', 'medium') or 'medium'
            self.profile_level = preset_data.get('profile_level', '') or ''
            self.pixel_format = preset_data.get('pixel_format', '') or ''
            self.tune = preset_data.get('tune', '') or ''
            self.threads = int(preset_data.get('threads', 0) or 0)
            self.keyint = int(preset_data.get('keyint', 0) or 0)
            v = preset_data.get('tag_hvc1', False)
            self.tag_hvc1 = (v is True) or (str(v).strip() == "1")
            v = preset_data.get('vf_lanczos', False)
            self.vf_lanczos = (v is True) or (str(v).strip() == "1")
            self.extra_args = preset_data.get('extra_args', '') or ''

    def getStatusText(self):
        """Возвращает текстовое представление статуса"""
        base = self.STATUS_LABELS.get(self.status, "❓ Неизвестно")
        if getattr(self, "output_renamed", False) and self.status in (QueueItem.STATUS_PROCESSING, QueueItem.STATUS_SUCCESS):
            if self.status == QueueItem.STATUS_SUCCESS:
                return "✅ Успех (переименован)"
            return "🔄 Переименован"
        return base
