"""Класс для элемента очереди кодирования"""

class QueueItem:
    """Представляет один файл в очереди кодирования"""
    
    # Статусы обработки
    STATUS_WAITING = "waiting"      # ⏳ Ожидание запуска
    STATUS_PROCESSING = "processing"  # 🔄 В процессе
    STATUS_SUCCESS = "success"      # ✅ Успех
    STATUS_ERROR = "error"          # ❌ Ошибка
    STATUS_PAUSED = "paused"         # ⏸ Приостановлено
    
    def __init__(self, file_path):
        self.file_path = file_path  # Полный путь к входному файлу
        # По умолчанию для файла используется пресет "default"
        # (перекодирование без изменения параметров, только другое имя файла)
        self.preset_name = "default"     # Имя пресета: "default", пользовательский или "custom"
        self.status = QueueItem.STATUS_WAITING
        self.progress = 0            # 0-100
        self.output_file = ""        # Путь к выходному файлу
        self.error_message = ""      # Сообщение об ошибке (если есть)
        self.output_renamed = False  # True, если выходной путь был изменён из-за существующего файла

        # Обрезка / склейка: области (start_sec, end_sec), которые остаются в финальном видео
        self.keep_segments = []      # [(start, end), ...] в секундах
        self.trim_start_sec = None   # Начало текущей области (кнопка In)
        self.trim_end_sec = None     # Конец текущей области (кнопка Out)
        
        # Параметры кодирования (могут быть из пресета или заданы вручную для файла)
        # Значения:
        # - "default"  – использовать параметры по умолчанию (как базовая команда)
        # - "current"  – не менять этот параметр относительно исходного файла
        # - конкретные значения, например "libx264", "mkv", "1920:1080" и т.п.
        self.codec = "default"
        self.container = "default"
        self.resolution = "default"
        self.custom_resolution = ""
        self.audio_codec = "current"

        # Основные настройки (0 или "" = не задано / по умолчанию)
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
        self.keyint = 0   # 0 = не задано, >0 = значение -g для FFmpeg
        self.tag_hvc1 = False
        self.vf_lanczos = False
        
        # Для паузы на Windows
        self.encoding_duration = 0   # Время кодирования до паузы
        self.video_duration = 0      # Длительность видео

        # Команда ffmpeg, привязанная к КОНКРЕТНОМУ элементу очереди
        # Это нужно, чтобы пользователь мог отредактировать команду для одного файла,
        # переключиться на другие файлы, а затем вернуться и увидеть свои правки.
        self.command = ""                    # Последняя отображённая команда для этого файла
        self.command_manually_edited = False # Флаг: команда редактировалась вручную
        self.last_generated_command = ""     # Последняя автоматически сгенерированная команда
    
    def setPreset(self, preset_data):
        """Устанавливает параметры из пресета"""
        if preset_data:
            self.codec = preset_data.get('codec', 'default')
            self.container = preset_data.get('container', 'default')
            self.resolution = preset_data.get('resolution', 'default')
            self.audio_codec = preset_data.get('audio_codec', 'aac')
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
            self.tag_hvc1 = bool(preset_data.get('tag_hvc1', False))
            self.vf_lanczos = bool(preset_data.get('vf_lanczos', False))
    
    def getStatusText(self):
        """Возвращает текстовое представление статуса"""
        status_map = {
            QueueItem.STATUS_WAITING: "⏳ Ожидание",
            QueueItem.STATUS_PROCESSING: "🔄 В процессе",
            QueueItem.STATUS_SUCCESS: "✅ Успех",
            QueueItem.STATUS_ERROR: "❌ Ошибка",
            QueueItem.STATUS_PAUSED: "⏸ Приостановлено"
        }
        base = status_map.get(self.status, "❓ Неизвестно")
        if getattr(self, "output_renamed", False) and self.status in (QueueItem.STATUS_PROCESSING, QueueItem.STATUS_SUCCESS):
            if self.status == QueueItem.STATUS_SUCCESS:
                return "✅ Успех (переименован)"
            return "🔄 Переименован"
        return base
