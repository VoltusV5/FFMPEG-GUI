# -*- coding: utf-8 -*-
"""Константы приложения: тема, размеры UI, магические числа."""

# Кодировка и формат JSON
JSON_ENCODING = "utf-8"
JSON_INDENT = 2

# Окно
WINDOW_TITLE = "FFmpeg GUI"
WINDOW_WIDTH = 1425
WINDOW_HEIGHT = 970

# Высота элементов (px)
HEIGHT_PRESET_EDITOR_CONTAINER = 311
HEIGHT_PRESET_EDITOR_LAYOUT = 298
HEIGHT_BUTTON_PRESET = 28
HEIGHT_TRIM_SEGMENT_BAR = 14
HEIGHT_WARNINGS_EXTRA = 100

# Ширина / размеры
TRIM_BAR_MIN_WIDTH = 100
LABEL_MIN_WIDTH = 100
QUEUE_TABLE_COLUMN_COUNT = 6
QUEUE_TABLE_COLUMN_WIDTHS_WITH_ROWS = (200, 200, 80, 100, 80, 78)
QUEUE_TABLE_COLUMN_WIDTHS_EMPTY = (215, 215, 80, 100, 80, 78)
PRESETS_TABLE_COLUMN_COUNT = 4
PRESETS_TABLE_DELETE_COLUMN_WIDTH = 70

# Отображение имён в таблице
MAX_DISPLAY_NAME_LENGTH = 25

# Таймеры (мс)
VIDEO_UPDATE_INTERVAL_MS = 100
PROCESS_NEXT_DELAY_MS = 500

# ETA
ETA_DELAY_SECONDS = 4
ETA_SMOOTHING_ALPHA = 0.15

# Прогресс (0–100)
PROGRESS_MAX = 100
PROGRESS_MIN = 0

# Видео: шаг кадра (мс, ~33 при 30 fps)
FRAME_STEP_MS = 33

# Сетка редактора пресетов
GRID_SPACING = 8
GRID_LABEL_WIDTH = 100
GRID_MARGINS_WARNINGS = (0, 8, 0, 0)
GRID_SPACING_WARNINGS = 4
COL0_SPACING = 4
CONTAINER_LAYOUT_SPACING = 6

# TrimSegmentBar: радиус скругления, толщина метки "In"
TRIM_BAR_RADIUS = 4
TRIM_BAR_IN_MARK_MIN = 2
TRIM_BAR_IN_MARK_MAX = 6
TRIM_BAR_IN_MARK_DIV = 100

# Цвета темы (для виджетов, не из main.py palette)
COLOR_BG_STRIP = (0x40, 0x40, 0x40)      # фон полоски trim
COLOR_KEEP_SEGMENT = (56, 142, 60)       # зелёный — области склейки
COLOR_TRIM_ACCENT = (0x4a, 0x9e, 0xff)   # синий — in/out
COLOR_DROP_BORDER = "#606060"
COLOR_DROP_BG = "#2b2b2b"
COLOR_DROP_LABEL = "#9e9e9e"
COLOR_DROP_FONT_SIZE = 36

# Стили кнопок (run/abort, convert)
STYLE_RUN_BUTTON = (
    "background-color: #2e7d32; color: white; font-weight: bold; padding: 8px; border: 1px solid #1b5e20;"
)
STYLE_ABORT_BUTTON = (
    "background-color: #c62828; color: white; font-weight: bold; padding: 8px; border: 1px solid #b71c1c;"
)
STYLE_CONVERT_BUTTON = "background-color: #2e7d32; color: white; font-weight: bold; padding: 8px;"

# Палитра (main.py)
COLOR_WINDOW = "#2b2b2b"
COLOR_WINDOW_TEXT = "#e0e0e0"
COLOR_BASE = "#3c3c3c"
COLOR_ALTERNATE_BASE = "#363636"
COLOR_BUTTON = "#404040"
COLOR_HIGHLIGHT = "#4a9eff"
COLOR_HIGHLIGHTED_TEXT = "#ffffff"

# Имена конфигурационных файлов
CONFIG_CUSTOM_OPTIONS = "custom_options.json"
CONFIG_SAVED_COMMANDS = "saved_commands.json"
CONFIG_APP_CONFIG = "app_config.json"
CONFIG_PRESETS_XML = "presets.xml"

# Аудио: соответствие формата и кодека FFmpeg (общее для «Видео в аудио» и «Аудио конвертер»)
AUDIO_CODEC_MAP = {
    "mp3": "libmp3lame",
    "wav": "pcm_s16le",
    "m4a": "aac",
    "flac": "flac",
    "ogg": "libvorbis",
}

# Форматы «Видео в аудио» / «Аудио конвертер» (label, ext)
AUDIO_FORMATS = [("MP3", "mp3"), ("WAV", "wav"), ("M4A", "m4a"), ("FLAC", "flac"), ("OGG", "ogg")]

# Варианты качества (label, value)
AUDIO_QUALITY_OPTIONS = [
    ("Текущего файла", "copy"),
    ("320 kbps", "320"),
    ("192 kbps", "192"),
    ("128 kbps", "128"),
    ("64 kbps", "64"),
]
