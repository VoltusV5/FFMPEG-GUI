# FFMPEG GUI

FFMPEG GUI — десктопное приложение с графическим интерфейсом для работы с FFmpeg.
Поддерживает очередь конвертаций, пресеты, предпросмотр и логирование.

![Скрин приложения](/image/README/screen.png)

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

## Документация

- Руководство пользователя: [user guide.md](user%20guide.md), полное: [user guide full.md](user%20guide%20full.md)
- Структура модулей: [../mixins/MODULES.md](../mixins/MODULES.md)

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

Из **корня проекта** (где лежат `main.py` и `pysidedeploy.spec`), с активированным виртуальным окружением и установленным PySide6:

```bash
pyside6-deploy
```

Или явно указать конфиг:

```bash
pyside6-deploy --config-file pysidedeploy.spec
```

### Авто‑сборка с переносом DLL/PYD в `bin/`

Чтобы после сборки файлы `.dll` и `.pyd` оказались в папке `bin/`, используйте скрипт:

```bat
tools\build.bat
```

Скрипт:

- запускает `pyside6-deploy`;
- находит свежую папку `*.dist`;
- переносит `.dll/.pyd` в `bin/` (критичные DLL остаются рядом с exe).

> Приложение автоматически добавляет `bin/` в `PATH` и `sys.path`, поэтому библиотеки подхватываются без ручных настроек.

**Важно:** некоторые DLL должны лежать рядом с exe, иначе приложение не стартует (Windows загружает их до запуска Python).
По умолчанию рядом остаются:

- _ctypes.pyd, pyexpat.pyd

Сборка создаёт standalone-приложение (папка с exe и библиотеками) в каталоге, указанном в `exec_directory` в spec (по умолчанию — корень проекта). В сборку автоматически включается папка **presets/** (presets.xml, custom_options.json, saved_commands.json) — у пользователя будут базовые пресеты и настройки по умолчанию. Иконка берётся из `icon.ico`; настройки Windows — из секции `[windows]` в `pysidedeploy.spec`.
