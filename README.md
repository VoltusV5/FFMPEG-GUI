# FFMPEG GUI

Графическое приложение на PySide6 для конвертации видео и аудио файлов с помощью FFmpeg. Позволяет настраивать параметры конвертации через удобный графический интерфейс без необходимости работы с командной строкой.

## Описание

FFMPEG GUI — десктопное приложение с графическим интерфейсом для работы с FFmpeg.
Поддерживает очередь конвертаций, пресеты, предпросмотр и логирование.

## Требования

- Python 3.13.6
- PySide6
- FFmpeg:
  - файл `ffmpeg.exe` должен находиться в корневой директории проекта
  - **рекомендуется** также положить рядом `ffprobe.exe` (используется для более точной оценки прогресса кодирования)
    Инструкция по установке FFmpeg:
    - Заходим на официальный сайт ffmpeg [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html)
    - наводимся на значок Windows -> windows builds from gyan.dev (https://www.gyan.dev/ffmpeg/builds/) 
    - листаем ниже до "release builds" -> [https://github.com/GyanD/codexffmpeg/releases/](https://github.com/GyanD/codexffmpeg/releases/tag/8.0.1) 
    - скачиваем билд [ffmpeg-8.0.1-essentials_build.zip](https://github.com/GyanD/codexffmpeg/releases/download/8.0.1/ffmpeg-8.0.1-essentials_build.zip)
    - после скачивания распаковываем
    - заходим в папку bin
    - копируем ffprobe.exe и ffmpeg.exe в корень FFMPEG GUI

## Установка

1. Клонируйте репозиторий или скачайте проект
2. Перейдите в директорию проекта
3. Создайте виртуальное окружение:

```bash
python -m venv venv
```

4. Активируйте виртуальное окружение:

**Windows (bash):**

```powershell
. venv/Scripts/activate
```

**Linux/Mac:**

```bash
source venv/bin/activate
```

5. Установите зависимости:

```bash
pip install -r requirements.txt
```

6. Убедитесь, что файл `ffmpeg.exe` находится в корневой директории проекта

## Запуск

После установки зависимостей запустите приложение:

```bash
python main.py
```

## Разработка

### Редактирование интерфейса

Для редактирования интерфейса используйте Qt Designer:

```bash
pyside6-designer ui/mainwindow.ui
```

(из корня проекта; путь к .ui — `ui/mainwindow.ui`)

### Компиляция UI файла

После изменения `.ui` файла в дизайнере сгенерируйте Python код:

```bash
pyside6-uic ui/mainwindow.ui -o ui/ui_mainwindow.py
```

**Важно:** Делайте это каждый раз после изменения `.ui` файла в дизайнере.

## Сборка и деплой

Для создания исполняемого файла используйте:

```bash
pyside6-deploy --mode onefile --name OpenFF_GUI main.py
```

Эта команда создаст standalone исполняемый файл без консольного окна.

## Документация

- Руководство пользователя: [user guide.md](user%20guide.md), полное: [user guide full.md](user%20guide%20full.md)
- Структура модулей: [../mixins/MODULES.md](../mixins/MODULES.md)

## Структура проекта

```
FFMPEG_GUI/
├── .gitignore           # Git ignore
├── main.py              # Точка входа (вызов app.main.main())
├── app/                 # Точка входа и главное окно
│   ├── main.py          # Запуск приложения, тема, логирование
│   ├── mainwindow.py    # Главное окно (миксины: очередь, кодирование, пресеты, предпросмотр, аудио)
│   └── constants.py     # Константы приложения
├── ui/                  # Сгенерированный UI
│   ├── mainwindow.ui    # Файл интерфейса Qt Designer
│   └── ui_mainwindow.py # Сгенерированный код интерфейса
├── models/              # Модели и данные
│   ├── queueitem.py     # Модель элемента очереди
│   └── presetmanager.py # Управление пресетами (presets/presets.xml)
├── mixins/              # Миксины главного окна
│   ├── MODULES.md       # Описание модулей
│   ├── queue_ui.py, encoding_process.py, preset_editor_ui.py
│   ├── video_preview.py, audio_pages.py, config_warnings.py
│   └── ...
├── widgets/             # Переиспользуемые виджеты (TrimSegmentBar, FileDropArea)
├── presets/             # Пресеты и сохранённые данные
│   ├── presets.xml      # Пресеты кодирования
│   ├── custom_options.json  # Пользовательские контейнеры/кодеки/разрешения
│   └── saved_commands.json  # Сохранённые команды FFmpeg
├── docs/                # Документация
│   ├── README.md        # Этот файл
│   ├── user guide.md    # Руководство пользователя
│   └── user guide full.md
├── app_config.json      # Индекс последней вкладки (в корне)
├── pysidedeploy.spec, requirements.txt
└── ...
```
