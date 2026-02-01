# Структура модулей проекта

Краткое описание файлов и ответственности за функционал. Файл находится в папке `mixins/`.

## Точка входа и UI

| Файл | Назначение |
|------|------------|
| `main.py` | Запуск приложения, настройка темы и палитры, создание главного окна. |
| `ui_mainwindow.py` | Сгенерированный из `.ui` интерфейс главного окна (не редактировать вручную). |
| `mainwindow.ui` | Исходник Qt Designer для главного окна. |

## Константы и данные

| Файл | Назначение |
|------|------------|
| `constants.py` | Константы приложения: размеры окна, высоты/ширины виджетов, цвета темы, имена конфигов, кодировка JSON, маппинг аудио-форматов и т.д. |
| `queueitem.py` | Класс `QueueItem` — элемент очереди кодирования (путь, пресет, статус, сегменты обрезки, доп. параметры). |
| `presetmanager.py` | Класс `PresetManager` — работа с `presets.xml`: загрузка/сохранение/удаление/перемещение пресетов, импорт из файла. |

## Виджеты и миксины

| Файл/папка | Назначение |
|------------|------------|
| `widgets/` | Переиспользуемые виджеты UI. |
| `widgets/trim_segment_bar.py` | Полоска под слайдером: отображение областей обрезки (keep/trim). |
| `widgets/file_drop_area.py` | Область перетаскивания файлов (drag-and-drop) с кнопкой «+». |
| `mixins/` | Папка с миксинами главного окна. |
| `mixins/config_warnings.py` | Миксин `ConfigWarningsMixin`: загрузка/сохранение вкладки (`app_config.json`), проверка ffmpeg/ffprobe, предупреждения о правах на запись, сброс очереди при ошибке. |
| `mixins/queue_ui.py` | Миксин `QueueUIMixin`: таблица очереди, добавление/удаление/перемещение файлов, drag-and-drop, выделение. |
| `mixins/encoding_process.py` | Миксин `EncodingMixin`: построение команды FFmpeg, процесс очереди, прогресс, ETA, пауза/возобновление. |
| `mixins/preset_editor_ui.py` | Миксин `PresetEditorUIMixin`: редактор пресетов, пользовательские опции (контейнеры, кодеки, разрешения, аудио), сохранённые команды, импорт/экспорт. |
| `mixins/video_preview.py` | Миксин `VideoPreviewMixin`: инициализация плеера, загрузка видео, seek, trim/keep, полоска обрезки, отображение времени. |
| `mixins/audio_pages.py` | Миксин `AudioPagesMixin`: вкладки «Видео в аудио» и «Аудио конвертер». |

## Главное окно

| Файл | Назначение |
|------|------------|
| `mainwindow.py` | Класс `MainWindow(QueueUIMixin, EncodingMixin, PresetEditorUIMixin, VideoPreviewMixin, AudioPagesMixin, ConfigWarningsMixin, QMainWindow)` — создание UI и состояния, вызовы `initQueue`, `initPresetEditor`, `initVideoPreview`, подключение сигналов; общие методы: `closeEvent`, `updateStatus`, `_openFolderOrSelectFile`, `openOutputFolder`, `openFileLocation`, `copyCommand`. Метод `getSelectedQueueItem` предоставляется `QueueUIMixin`. |

## Конфигурационные файлы (в корне проекта)

- `custom_options.json` — пользовательские контейнеры, кодеки, разрешения, аудио-кодеки.
- `saved_commands.json` — сохранённые команды FFmpeg.
- `app_config.json` — индекс последней активной вкладки.
- `presets.xml` — пресеты кодирования.

## Где искать функционал

- **Очередь файлов** — `mixins/queue_ui.py`: `initQueue`, `addFilesToQueue`, `removeSelectedFromQueue`, `updateQueueTable`, `setupDragAndDrop`, `getSelectedQueueItem`, `onQueueItemSelected`, `_truncateNameForDisplay`, `_moveQueueItem`.
- **Редактор пресетов** — `mixins/preset_editor_ui.py`: `initPresetEditor`, `syncPresetEditorWithPresetData`, `syncPresetEditorWithQueueItem`, `updateCommandFromPresetEditor`, `_loadCustomOptions`, `_saveCustomOptions`, `_loadSavedCommands`, `_saveSavedCommands`, `_showCustom*Menu`, `refreshPresetsTable`, `createPreset`, `saveCurrentPreset`, `savePresetWithCustomParams`, `exportData`, `importData`, `saveCurrentCommand`, `loadSavedCommand`, `deleteSavedCommand`.
- **Построение команды FFmpeg и кодирование** — `mixins/encoding_process.py`: `generateFFmpegCommand`, `_getFFmpegArgs`, `processNextInQueue`, `readProcessOutput`, `processFinished`, ETA, пауза.
- **Предпросмотр видео** — `mixins/video_preview.py`: `initVideoPreview`, `loadVideoForPreview`, `seekVideo`, `setTrimStart`/`setTrimEnd`, `addKeepArea`, `_updateTrimSegmentBar`.
- **Вкладки «Видео в аудио» и «Аудио конвертер»** — `mixins/audio_pages.py`: `_createVideoToAudioPage`, `_createAudioConverterPage`, `_v2a*`, `_a2a*`, `_computeOutputPathForExtension`.
- **Конфиг и предупреждения** — `mixins/config_warnings.py`: `_loadAppConfig`, `_saveAppConfig`, `_checkToolsAvailability`, `_warnIfConfigPathNotWritable`, `_stopQueueWithError`.
