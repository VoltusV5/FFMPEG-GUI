"""Миксин: редактор пресетов, пользовательские опции, сохранённые команды, импорт/экспорт."""

import os
import json
import shutil
import logging
from PySide6.QtWidgets import (
    QMenu, QInputDialog, QMessageBox, QFileDialog,
    QVBoxLayout, QHBoxLayout, QGridLayout, QTableWidgetItem, QPushButton,
    QHeaderView, QAbstractItemView, QButtonGroup, QWidget, QLabel,
    QSpinBox, QComboBox, QCheckBox, QLineEdit, QSizePolicy,
)
from PySide6.QtCore import Qt

from app.constants import (
    CONFIG_PRESETS_XML, CONFIG_CUSTOM_OPTIONS, CONFIG_SAVED_COMMANDS,
    JSON_ENCODING, JSON_INDENT,
    PRESETS_TABLE_COLUMN_COUNT, PRESETS_TABLE_DELETE_COLUMN_WIDTH, PRESETS_TABLE_BUTTON_HEIGHT,
    FPS_SPIN_MAX, BITRATE_SPIN_STEP, PROFILE_LEVEL_MIN_WIDTH,
    GRID_SPACING, LABEL_MIN_WIDTH, HEIGHT_WARNINGS_EXTRA,
    GRID_MARGINS_WARNINGS, GRID_SPACING_WARNINGS, CONTAINER_LAYOUT_SPACING, COL0_SPACING,
)
from models.queueitem import QueueItem

logger = logging.getLogger(__name__)


class PresetEditorUIMixin:
    """Миксин: редактор пресетов, custom options, saved commands, импорт/экспорт."""

    def _loadCustomOptions(self):
        """Загружает списки пользовательских опций из custom_options.json."""
        if not os.path.exists(self._customOptionsPath):
            return
        try:
            with open(self._customOptionsPath, "r", encoding=JSON_ENCODING) as f:
                data = json.load(f)
            self.customContainers = data.get("containers", [])
            if not isinstance(self.customContainers, list):
                self.customContainers = []
            self.customCodecs = data.get("codecs", [])
            if not isinstance(self.customCodecs, list):
                self.customCodecs = []
            self.customResolutions = data.get("resolutions", [])
            if not isinstance(self.customResolutions, list):
                self.customResolutions = []
            self.customAudioCodecs = data.get("audio_codecs", [])
            if not isinstance(self.customAudioCodecs, list):
                self.customAudioCodecs = []
        except Exception:
            self.customContainers = []
            self.customCodecs = []
            self.customResolutions = []
            self.customAudioCodecs = []

    def _saveCustomOptions(self):
        """Сохраняет списки пользовательских опций в custom_options.json."""
        try:
            data = {
                "containers": getattr(self, "customContainers", []),
                "codecs": getattr(self, "customCodecs", []),
                "resolutions": getattr(self, "customResolutions", []),
                "audio_codecs": getattr(self, "customAudioCodecs", []),
            }
            with open(self._customOptionsPath, "w", encoding=JSON_ENCODING) as f:
                json.dump(data, f, ensure_ascii=False, indent=JSON_INDENT)
        except Exception:
            logger.exception("Ошибка сохранения custom_options")
            self._warnConfigWriteFailure(CONFIG_CUSTOM_OPTIONS)

    def _loadSavedCommands(self):
        """Загружает список сохранённых команд из saved_commands.json."""
        if not os.path.exists(self._savedCommandsPath):
            return []
        try:
            with open(self._savedCommandsPath, "r", encoding=JSON_ENCODING) as f:
                data = json.load(f)
            lst = data.get("commands", [])
            if not isinstance(lst, list):
                return []
            return [x for x in lst if isinstance(x, dict) and x.get("name") and x.get("command") is not None]
        except Exception:
            return []

    def _saveSavedCommands(self, commands_list):
        """Сохраняет список сохранённых команд в saved_commands.json."""
        try:
            data = {"commands": commands_list}
            with open(self._savedCommandsPath, "w", encoding=JSON_ENCODING) as f:
                json.dump(data, f, ensure_ascii=False, indent=JSON_INDENT)
        except Exception:
            logger.exception("Ошибка сохранения saved_commands")
            self._warnConfigWriteFailure(CONFIG_SAVED_COMMANDS)

    def _showCustomContainerMenu(self):
        btn = getattr(self.ui, "containerCustomButton", None)
        if btn is None:
            return
        menu = QMenu(self)
        current = (self.currentContainerCustom or "").lower()
        for name in self.customContainers:
            if not name or not isinstance(name, str):
                continue
            action = menu.addAction(name)
            action.setCheckable(True)
            if name.lower() == current:
                action.setChecked(True)
            action.triggered.connect(lambda checked=False, n=name: self._onCustomContainerSelected(n))
        menu.addSeparator()
        menu.addAction("Добавить…").triggered.connect(self._onAddCustomContainer)
        menu.addAction("Удалить…").triggered.connect(self._onDeleteCustomContainer)
        menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))

    def _onCustomContainerSelected(self, name):
        self.currentContainerCustom = name
        if hasattr(self.ui, "containerCustomButton"):
            self.ui.containerCustomButton.setChecked(True)
        self.updateCommandFromPresetEditor()

    def _onAddCustomContainer(self):
        text, ok = QInputDialog.getText(
            self, "Пользовательский контейнер",
            "Введите расширение контейнера (например, mov):",
            text=self.currentContainerCustom or "mp4"
        )
        if ok and text.strip():
            name = text.strip().lstrip(".").lower()
            if name and name not in self.customContainers:
                self.customContainers.append(name)
                self._saveCustomOptions()
            self.currentContainerCustom = name
            if hasattr(self.ui, "containerCustomButton"):
                self.ui.containerCustomButton.setChecked(True)
            self.updateCommandFromPresetEditor()

    def _onDeleteCustomContainer(self):
        if not self.customContainers:
            QMessageBox.information(self, "Контейнеры", "Нет пользовательских контейнеров.")
            return
        name, ok = QInputDialog.getItem(self, "Удалить контейнер", "Выберите контейнер:", self.customContainers, 0, False)
        if not ok or not name:
            return
        self.customContainers = [c for c in self.customContainers if c != name]
        self._saveCustomOptions()
        if self.currentContainerCustom == name:
            self.currentContainerCustom = ""
            if hasattr(self.ui, "containerCurrentButton"):
                self.ui.containerCurrentButton.setChecked(True)
        self.updateCommandFromPresetEditor()

    def _showCustomCodecMenu(self):
        btn = getattr(self.ui, "codecCustomButton", None)
        if btn is None:
            return
        menu = QMenu(self)
        current = (self.currentCodecCustom or "").lower()
        for name in getattr(self, "customCodecs", []):
            if not name or not isinstance(name, str):
                continue
            action = menu.addAction(name)
            action.setCheckable(True)
            if name.lower() == current:
                action.setChecked(True)
            action.triggered.connect(lambda checked=False, n=name: self._onCustomCodecSelected(n))
        menu.addSeparator()
        menu.addAction("Добавить…").triggered.connect(self._onAddCustomCodec)
        menu.addAction("Удалить…").triggered.connect(self._onDeleteCustomCodec)
        menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))

    def _onCustomCodecSelected(self, name):
        self.currentCodecCustom = name
        if hasattr(self.ui, "codecCustomButton"):
            self.ui.codecCustomButton.setChecked(True)
        self.updateCommandFromPresetEditor()

    def _onAddCustomCodec(self):
        text, ok = QInputDialog.getText(
            self, "Пользовательский кодек", "Введите имя видеокодека (например, libx264):",
            text=self.currentCodecCustom or "libx264"
        )
        if ok and text.strip():
            name = text.strip()
            if name not in self.customCodecs:
                self.customCodecs.append(name)
                self._saveCustomOptions()
            self.currentCodecCustom = name
            if hasattr(self.ui, "codecCustomButton"):
                self.ui.codecCustomButton.setChecked(True)
            self.updateCommandFromPresetEditor()

    def _onDeleteCustomCodec(self):
        if not self.customCodecs:
            QMessageBox.information(self, "Кодеки", "Нет пользовательских кодеков.")
            return
        name, ok = QInputDialog.getItem(self, "Удалить кодек", "Выберите кодек:", self.customCodecs, 0, False)
        if not ok or not name:
            return
        self.customCodecs = [c for c in self.customCodecs if c != name]
        self._saveCustomOptions()
        if self.currentCodecCustom == name:
            self.currentCodecCustom = ""
            if hasattr(self.ui, "codecCurrentButton"):
                self.ui.codecCurrentButton.setChecked(True)
        self.updateCommandFromPresetEditor()

    def _showCustomResolutionMenu(self):
        btn = getattr(self.ui, "resolutionCustomButton", None)
        if btn is None:
            return
        menu = QMenu(self)
        current = (self.currentResolutionCustom or "").replace(" ", "")
        for name in getattr(self, "customResolutions", []):
            if not name or not isinstance(name, str):
                continue
            norm = name.replace(" ", "")
            action = menu.addAction(name)
            action.setCheckable(True)
            if norm == current or norm == current.replace(":", "x"):
                action.setChecked(True)
            action.triggered.connect(lambda checked=False, n=name: self._onCustomResolutionSelected(n))
        menu.addSeparator()
        menu.addAction("Добавить…").triggered.connect(self._onAddCustomResolution)
        menu.addAction("Удалить…").triggered.connect(self._onDeleteCustomResolution)
        menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))

    def _onCustomResolutionSelected(self, name):
        self.currentResolutionCustom = name.strip().replace("x", ":").replace(" ", "")
        if hasattr(self.ui, "resolutionCustomButton"):
            self.ui.resolutionCustomButton.setChecked(True)
        self.updateCommandFromPresetEditor()

    def _onAddCustomResolution(self):
        text, ok = QInputDialog.getText(
            self, "Пользовательское разрешение", "Введите разрешение (например, 1920:1080 или 1920x1080):",
            text=self.currentResolutionCustom or "1920:1080"
        )
        if ok and text.strip():
            name = text.strip().replace("x", ":").replace(" ", "")
            if name not in self.customResolutions:
                self.customResolutions.append(name)
                self._saveCustomOptions()
            self.currentResolutionCustom = name
            if hasattr(self.ui, "resolutionCustomButton"):
                self.ui.resolutionCustomButton.setChecked(True)
            self.updateCommandFromPresetEditor()

    def _onDeleteCustomResolution(self):
        if not self.customResolutions:
            QMessageBox.information(self, "Разрешения", "Нет пользовательских разрешений.")
            return
        name, ok = QInputDialog.getItem(self, "Удалить разрешение", "Выберите разрешение:", self.customResolutions, 0, False)
        if not ok or not name:
            return
        self.customResolutions = [r for r in self.customResolutions if r != name]
        self._saveCustomOptions()
        if self.currentResolutionCustom.replace("x", ":") == name.replace("x", ":"):
            self.currentResolutionCustom = ""
            if hasattr(self.ui, "resolutionCurrentButton"):
                self.ui.resolutionCurrentButton.setChecked(True)
        self.updateCommandFromPresetEditor()

    def _showCustomAudioCodecMenu(self):
        btn = getattr(self, "_audioCodecCustomButton", None)
        if btn is None:
            return
        menu = QMenu(self)
        current = (self.currentAudioCodecCustom or "").lower()
        for name in getattr(self, "customAudioCodecs", []):
            if not name or not isinstance(name, str):
                continue
            action = menu.addAction(name)
            action.setCheckable(True)
            if name.lower() == current:
                action.setChecked(True)
            action.triggered.connect(lambda checked=False, n=name: self._onCustomAudioCodecSelected(n))
        menu.addSeparator()
        menu.addAction("Добавить…").triggered.connect(self._onAddCustomAudioCodec)
        menu.addAction("Удалить…").triggered.connect(self._onDeleteCustomAudioCodec)
        menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))

    def _onCustomAudioCodecSelected(self, name):
        self.currentAudioCodecCustom = name
        if hasattr(self, "_audioCodecCustomButton"):
            self._audioCodecCustomButton.setChecked(True)
        self.updateCommandFromPresetEditor()

    def _onAddCustomAudioCodec(self):
        text, ok = QInputDialog.getText(
            self, "Пользовательский аудио-кодек", "Введите имя аудио-кодека (например, aac, libopus):",
            text=self.currentAudioCodecCustom or "aac"
        )
        if ok and text.strip():
            name = text.strip()
            if name not in self.customAudioCodecs:
                self.customAudioCodecs.append(name)
                self._saveCustomOptions()
            self.currentAudioCodecCustom = name
            if hasattr(self, "_audioCodecCustomButton"):
                self._audioCodecCustomButton.setChecked(True)
            self.updateCommandFromPresetEditor()

    def _onDeleteCustomAudioCodec(self):
        if not self.customAudioCodecs:
            QMessageBox.information(self, "Аудио‑кодеки", "Нет пользовательских аудио‑кодеков.")
            return
        name, ok = QInputDialog.getItem(self, "Удалить аудио‑кодек", "Выберите аудио‑кодек:", self.customAudioCodecs, 0, False)
        if not ok or not name:
            return
        self.customAudioCodecs = [c for c in self.customAudioCodecs if c != name]
        self._saveCustomOptions()
        if self.currentAudioCodecCustom == name:
            self.currentAudioCodecCustom = ""
            if hasattr(self, "_audioCodecCurrentButton"):
                self._audioCodecCurrentButton.setChecked(True)
        self.updateCommandFromPresetEditor()

    def initPresetEditor(self):
        """Настраивает таблицу пресетов и группы кнопок codec/container/resolution."""
        if not hasattr(self.ui, 'presetsTableWidget'):
            return

        table = self.ui.presetsTableWidget
        table.setColumnCount(PRESETS_TABLE_COLUMN_COUNT)
        table.setHorizontalHeaderLabels(["Название", "Описание", "Удалить", "Применить"])
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Fixed)
        table.setColumnWidth(0, 125)
        table.setColumnWidth(1, 278)
        table.setColumnWidth(2, PRESETS_TABLE_DELETE_COLUMN_WIDTH)
        table.setColumnWidth(3, 88)

        self.codecButtonGroup = QButtonGroup(self)
        self.codecButtonGroup.setExclusive(True)
        for attr in ['codecCurrentButton', 'codecLibx264Button', 'codecLibx265Button', 'codecCustomButton']:
            if hasattr(self.ui, attr):
                btn = getattr(self.ui, attr)
                btn.setCheckable(True)
                self.codecButtonGroup.addButton(btn)
        codec_idx = self.ui.codecRowLayout.indexOf(self.ui.codecCustomButton)
        for name, text in [("Prores", "prores")]:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setObjectName(f"codec{name}Button")
            self.ui.codecRowLayout.insertWidget(codec_idx, btn)
            self.codecButtonGroup.addButton(btn)
            setattr(self, f"_codec{name}Button", btn)
            codec_idx += 1
        if hasattr(self, 'codecButtonGroup'):
            self.codecButtonGroup.buttonClicked.connect(self.onCodecButtonClicked)

        self.containerButtonGroup = QButtonGroup(self)
        self.containerButtonGroup.setExclusive(True)
        for attr in ['containerCurrentButton', 'containerMp4Button', 'containerMkvButton', 'containerCustomButton']:
            if hasattr(self.ui, attr):
                btn = getattr(self.ui, attr)
                btn.setCheckable(True)
                self.containerButtonGroup.addButton(btn)
        idx = self.ui.containerRowLayout.indexOf(self.ui.containerCustomButton)
        for name, text in [("Mov", "mov"), ("Avi", "avi"), ("Mxf", "mxf")]:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setObjectName(f"container{name}Button")
            self.ui.containerRowLayout.insertWidget(idx, btn)
            self.containerButtonGroup.addButton(btn)
            setattr(self, f"_container{name}Button", btn)
            idx += 1
        if hasattr(self, 'containerButtonGroup'):
            self.containerButtonGroup.buttonClicked.connect(self.onContainerButtonClicked)

        self.resolutionButtonGroup = QButtonGroup(self)
        self.resolutionButtonGroup.setExclusive(True)
        for attr in ['resolutionCurrentButton', 'resolution480pButton', 'resolution720pButton', 'resolution1080pButton', 'resolutionCustomButton']:
            if hasattr(self.ui, attr):
                btn = getattr(self.ui, attr)
                btn.setCheckable(True)
                self.resolutionButtonGroup.addButton(btn)
        res_idx = self.ui.resolutionRowLayout.indexOf(self.ui.resolutionCustomButton)
        for name, text in [("2k", "2k"), ("4k", "4k")]:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setObjectName(f"resolution{name.upper()}Button")
            self.ui.resolutionRowLayout.insertWidget(res_idx, btn)
            self.resolutionButtonGroup.addButton(btn)
            setattr(self, f"_resolution{name}Button", btn)
            res_idx += 1
        if hasattr(self, 'resolutionButtonGroup'):
            self.resolutionButtonGroup.buttonClicked.connect(self.onResolutionButtonClicked)

        self.audioCodecButtonGroup = QButtonGroup(self)
        self.audioCodecButtonGroup.setExclusive(True)
        audio_row = QHBoxLayout()
        audio_row.setSpacing(5)
        audio_row.addWidget(QLabel("Аудио-кодеки:"))
        for name, text in [("Current", "current"), ("Aac", "aac"), ("Mp3", "mp3"), ("Pcm16", "pcm_s16le"), ("Pcm24", "pcm_s24le"), ("Custom", "custom")]:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setObjectName(f"audioCodec{name}Button")
            audio_row.addWidget(btn)
            self.audioCodecButtonGroup.addButton(btn)
            setattr(self, f"_audioCodec{name}Button", btn)
        self._audioCodecCurrentButton.setChecked(True)
        self.ui.presetSettingsLayout.addLayout(audio_row)
        self.audioCodecButtonGroup.buttonClicked.connect(self.onAudioCodecButtonClicked)

        parent_4 = self.ui.verticalLayoutWidget_4
        grid = QGridLayout()
        grid.setSpacing(GRID_SPACING)
        label_w = LABEL_MIN_WIDTH
        field_w = 72

        l0 = QLabel("CRF:")
        l0.setMinimumWidth(label_w)
        grid.addWidget(l0, 0, 0)
        self._crfSpin = QSpinBox(parent_4)
        self._crfSpin.setRange(0, 51)
        self._crfSpin.setSpecialValueText("—")
        self._crfSpin.setMinimumWidth(field_w)
        grid.addWidget(self._crfSpin, 0, 1)
        l1 = QLabel("Bitrate (k):")
        l1.setMinimumWidth(label_w)
        grid.addWidget(l1, 0, 2)
        self._bitrateSpin = QSpinBox(parent_4)
        self._bitrateSpin.setRange(0, 100000)
        self._bitrateSpin.setValue(0)
        self._bitrateSpin.setSpecialValueText("—")
        self._bitrateSpin.setSingleStep(BITRATE_SPIN_STEP)
        self._bitrateSpin.setMinimumWidth(field_w)
        grid.addWidget(self._bitrateSpin, 0, 3)
        l2 = QLabel("FPS:")
        l2.setMinimumWidth(label_w)
        grid.addWidget(l2, 0, 4)
        self._fpsSpin = QSpinBox(parent_4)
        self._fpsSpin.setRange(0, FPS_SPIN_MAX)
        self._fpsSpin.setValue(0)
        self._fpsSpin.setSpecialValueText("—")
        self._fpsSpin.setMinimumWidth(field_w)
        grid.addWidget(self._fpsSpin, 0, 5)

        l3 = QLabel("Аудио битрейт (k):")
        l3.setMinimumWidth(label_w / 2 + 50)
        grid.addWidget(l3, 1, 0)
        self._audioBitrateSpin = QSpinBox(parent_4)
        self._audioBitrateSpin.setRange(0, 2000)
        self._audioBitrateSpin.setValue(0)
        self._audioBitrateSpin.setSpecialValueText("—")
        self._audioBitrateSpin.setMinimumWidth(field_w)
        grid.addWidget(self._audioBitrateSpin, 1, 1)
        l4 = QLabel("Частота (Hz):")
        l4.setMinimumWidth(label_w)
        grid.addWidget(l4, 1, 2)
        self._sampleRateSpin = QSpinBox(parent_4)
        self._sampleRateSpin.setRange(0, 192000)
        self._sampleRateSpin.setValue(0)
        self._sampleRateSpin.setSpecialValueText("—")
        self._sampleRateSpin.setMinimumWidth(field_w)
        grid.addWidget(self._sampleRateSpin, 1, 3)
        l5 = QLabel("Keyint:")
        l5.setMinimumWidth(label_w)
        grid.addWidget(l5, 1, 4)
        self._keyintSpin = QSpinBox(parent_4)
        self._keyintSpin.setRange(0, 10000)
        self._keyintSpin.setValue(0)
        self._keyintSpin.setSpecialValueText("—")
        self._keyintSpin.setMinimumWidth(field_w)
        self._keyintSpin.setToolTip("Интервал ключевых кадров (-g), 0 = не задано")
        grid.addWidget(self._keyintSpin, 1, 5)

        l6 = QLabel("Profile/Level:")
        l6.setMinimumWidth(label_w)
        grid.addWidget(l6, 2, 0)
        self._profileLevelEdit = QLineEdit(parent_4)
        self._profileLevelEdit.setPlaceholderText("high:4.1…")
        self._profileLevelEdit.setMinimumWidth(PROFILE_LEVEL_MIN_WIDTH)
        grid.addWidget(self._profileLevelEdit, 2, 1)
        l7 = QLabel("Pixel format:")
        l7.setMinimumWidth(label_w)
        grid.addWidget(l7, 2, 2)
        self._pixelFormatEdit = QLineEdit(parent_4)
        self._pixelFormatEdit.setPlaceholderText("yuv420p")
        self._pixelFormatEdit.setMinimumWidth(80)
        grid.addWidget(self._pixelFormatEdit, 2, 3)
        l8 = QLabel("Tune:")
        l8.setMinimumWidth(label_w)
        grid.addWidget(l8, 2, 4)
        self._tuneEdit = QLineEdit(parent_4)
        self._tuneEdit.setPlaceholderText("film…")
        self._tuneEdit.setMinimumWidth(80)
        grid.addWidget(self._tuneEdit, 2, 5)

        col0_widget = QWidget(parent_4)
        col0_layout = QVBoxLayout(col0_widget)
        col0_layout.setContentsMargins(0, 0, 0, 0)
        col0_layout.setSpacing(COL0_SPACING)
        self._checkTagHvc1 = QCheckBox(parent_4)
        self._checkTagHvc1.setText("-tag:v hvc1")
        self._checkTagHvc1.setToolTip("Для совместимости HEVC")
        col0_layout.addWidget(self._checkTagHvc1)
        self._checkVfLanczos = QCheckBox(parent_4)
        self._checkVfLanczos.setText(":flags=lanczos")
        self._checkVfLanczos.setToolTip("алгоритм масштабирования")
        col0_layout.addWidget(self._checkVfLanczos)
        grid.addWidget(col0_widget, 3, 0, 1, 2)
        l_preset = QLabel("Preset:")
        l_preset.setMinimumWidth(label_w)
        grid.addWidget(l_preset, 3, 2)
        self._presetCombo = QComboBox(parent_4)
        for p in ["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow", "placebo"]:
            self._presetCombo.addItem(p)
        self._presetCombo.setCurrentIndex(5)
        self._presetCombo.setMinimumWidth(PROFILE_LEVEL_MIN_WIDTH)
        grid.addWidget(self._presetCombo, 3, 3)
        l_threads = QLabel("Threads:")
        l_threads.setMinimumWidth(label_w)
        grid.addWidget(l_threads, 3, 4)
        self._threadsSpin = QSpinBox(parent_4)
        self._threadsSpin.setRange(0, 64)
        self._threadsSpin.setValue(0)
        self._threadsSpin.setSpecialValueText("auto")
        self._threadsSpin.setMinimumWidth(80)
        grid.addWidget(self._threadsSpin, 3, 5)

        self.ui.presetSettingsLayout.addLayout(grid)

        self._spinSelectAllOnFocus.add(self._bitrateSpin)
        self._bitrateSpin.installEventFilter(self)

        self.ui.presetSettingsLayout.addStretch(1)

        self._warningsExtraContainer = QWidget(self.ui.presetSettingsContainer)
        self._warningsExtraContainer.setMaximumHeight(HEIGHT_WARNINGS_EXTRA)
        self._warningsExtraContainer.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self._warningsExtraLayout = QVBoxLayout(self._warningsExtraContainer)
        self._warningsExtraLayout.setContentsMargins(*GRID_MARGINS_WARNINGS)
        self._warningsExtraLayout.setSpacing(GRID_SPACING_WARNINGS)

        self._warningLabel = QLabel("")
        self._warningLabel.setStyleSheet("color: #ff6666;")
        self._warningLabel.setWordWrap(True)
        self._warningLabel.hide()
        self._warningsExtraLayout.addWidget(self._warningLabel)

        self._extraLabel = QLabel("")
        self._extraLabel.setStyleSheet("color: #8fb5ff;")
        self._extraLabel.setWordWrap(True)
        self._extraLabel.hide()
        self._warningsExtraLayout.addWidget(self._extraLabel)

        container_layout = self.ui.presetSettingsContainer.layout()
        if container_layout is None:
            container_layout = QVBoxLayout(self.ui.presetSettingsContainer)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(CONTAINER_LAYOUT_SPACING)
            container_layout.addWidget(self.ui.verticalLayoutWidget_4, 1)
        container_layout.addWidget(self._warningsExtraContainer, 0)

        combo_style = (
            "QComboBox::drop-down {"
            "  background-color: #2f2f2f;"
            "  border-left: 1px solid #505050;"
            "  width: 18px;"
            "}"
        )
        self._presetCombo.setStyleSheet(combo_style)

        for w in (self._crfSpin, self._bitrateSpin, self._fpsSpin, self._audioBitrateSpin, self._sampleRateSpin,
                  self._keyintSpin, self._presetCombo, self._profileLevelEdit, self._pixelFormatEdit, self._tuneEdit, self._threadsSpin,
                  self._checkTagHvc1, self._checkVfLanczos):
            if hasattr(w, 'valueChanged'):
                w.valueChanged.connect(self.updateCommandFromPresetEditor)
            elif hasattr(w, 'currentIndexChanged'):
                w.currentIndexChanged.connect(self.updateCommandFromPresetEditor)
            elif hasattr(w, 'textChanged'):
                w.textChanged.connect(self.updateCommandFromPresetEditor)
            elif hasattr(w, 'stateChanged'):
                w.stateChanged.connect(self.updateCommandFromPresetEditor)

        if hasattr(self, 'codecButtonGroup'):
            self.codecButtonGroup.buttonClicked.connect(self.updateCommandFromPresetEditor)
        if hasattr(self, 'containerButtonGroup'):
            self.containerButtonGroup.buttonClicked.connect(self.updateCommandFromPresetEditor)
        if hasattr(self, 'resolutionButtonGroup'):
            self.resolutionButtonGroup.buttonClicked.connect(self.updateCommandFromPresetEditor)

        if hasattr(self.ui, 'presetsTableWidget'):
            self.ui.presetsTableWidget.itemSelectionChanged.connect(self.onPresetTableSelectionChanged)

        if hasattr(self.ui, 'codecCurrentButton'):
            self.ui.codecCurrentButton.setChecked(True)
        if hasattr(self.ui, 'containerCurrentButton'):
            self.ui.containerCurrentButton.setChecked(True)
        if hasattr(self.ui, 'resolutionCurrentButton'):
            self.ui.resolutionCurrentButton.setChecked(True)

        self.refreshPresetsTable()

    def updateCommandFromGUI(self):
        """Обновляет команду только если она не была отредактирована вручную."""
        item = self.getSelectedQueueItem()
        if not item:
            if hasattr(self.ui, 'commandDisplay'):
                self.ui.commandDisplay.setPlainText("ffmpeg")
            return
        if not self.commandManuallyEdited:
            new_cmd = self.generateFFmpegCommand()
            self.lastGeneratedCommand = new_cmd
            if hasattr(self.ui, 'commandDisplay'):
                cmd_widget = self.ui.commandDisplay
                cmd_widget.blockSignals(True)
                cmd_widget.setPlainText(new_cmd)
                cmd_widget.blockSignals(False)
            item.last_generated_command = new_cmd
            item.command = new_cmd
            item.command_manually_edited = False
        else:
            item.command = self.ui.commandDisplay.toPlainText()

    def onCommandManuallyEdited(self):
        """Отслеживает ручное редактирование команды."""
        item = self.getSelectedQueueItem()
        if not item:
            return
        current_cmd = self.ui.commandDisplay.toPlainText()
        last_generated = getattr(item, "last_generated_command", self.lastGeneratedCommand)
        prev_manual = getattr(item, "command_manually_edited", False)
        prev_preset = item.preset_name
        if current_cmd != last_generated:
            self.commandManuallyEdited = True
            item.command_manually_edited = True
            item.command = current_cmd
            if not (isinstance(item.preset_name, str) and item.preset_name.startswith("cmd:")):
                item.preset_name = "custom"
            if (not prev_manual) or (prev_preset != item.preset_name):
                self.updateQueueTable()
        else:
            self.commandManuallyEdited = False
            item.command_manually_edited = False
            if prev_manual:
                self.updateQueueTable()

    def refreshPresetsTable(self):
        if not hasattr(self.ui, 'presetsTableWidget'):
            return
        table = self.ui.presetsTableWidget
        presets = self.presetManager.loadAllPresets()
        table.setRowCount(len(presets))
        for row, p in enumerate(presets):
            name_text = p["name"]
            extra_hint = p.get("extra_args", "") or ""
            if extra_hint.strip():
                name_text = f"{p['name']} +extra"
            name_item = QTableWidgetItem(name_text)
            desc_item = QTableWidgetItem(p.get("description", ""))
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            desc_item.setFlags(desc_item.flags() & ~Qt.ItemIsEditable)
            name_item.setToolTip(p["name"])
            name_item.setData(Qt.UserRole, p["name"])
            desc_tooltip = p.get("description", "")
            if extra_hint.strip():
                desc_tooltip = (desc_tooltip + "\n" if desc_tooltip else "") + f"Extra: {extra_hint}"
            desc_item.setToolTip(desc_tooltip)
            table.setItem(row, 0, name_item)
            table.setItem(row, 1, desc_item)
            delete_btn = QPushButton("Удалить")
            delete_btn.setMaximumHeight(PRESETS_TABLE_BUTTON_HEIGHT)
            delete_btn.setStyleSheet("padding: 1px 4px; font-size: 10px; min-height: 0;")
            delete_btn.clicked.connect(lambda _, n=p["name"]: self.onDeletePresetClicked(n))
            table.setCellWidget(row, 2, delete_btn)
            apply_btn = QPushButton("Применить")
            apply_btn.setMaximumHeight(PRESETS_TABLE_BUTTON_HEIGHT)
            apply_btn.setStyleSheet("padding: 1px 4px; font-size: 10px; min-height: 0;")
            apply_btn.clicked.connect(lambda _, n=p["name"]: self.onApplyPresetClicked(n))
            table.setCellWidget(row, 3, apply_btn)

    def _getSelectedPresetName(self):
        if not hasattr(self.ui, 'presetsTableWidget'):
            return None, -1
        table = self.ui.presetsTableWidget
        row = table.currentRow()
        if row < 0:
            return None, -1
        name_item = table.item(row, 0)
        if not name_item:
            return None, -1
        return name_item.data(Qt.UserRole) or name_item.text(), row

    def movePresetUp(self):
        name, row = self._getSelectedPresetName()
        if not name:
            return
        if self.presetManager.movePreset(name, "up"):
            self.refreshPresetsTable()
            if hasattr(self.ui, 'presetsTableWidget'):
                self.ui.presetsTableWidget.setCurrentCell(max(row - 1, 0), 0)
                self.onPresetTableSelectionChanged()

    def movePresetDown(self):
        name, row = self._getSelectedPresetName()
        if not name:
            return
        if self.presetManager.movePreset(name, "down"):
            self.refreshPresetsTable()
            if hasattr(self.ui, 'presetsTableWidget'):
                table = self.ui.presetsTableWidget
                new_row = min(row + 1, table.rowCount() - 1)
                table.setCurrentCell(new_row, 0)
                self.onPresetTableSelectionChanged()

    def onDeletePresetClicked(self, name):
        if not name:
            return
        ret = QMessageBox.question(
            self, "Удаление пресета", f'Удалить пресет "{name}"?',
            QMessageBox.Yes | QMessageBox.No
        )
        if ret != QMessageBox.Yes:
            return
        self.presetManager.removePreset(name)
        self.refreshPresetsTable()

    def onPresetTableSelectionChanged(self):
        if not hasattr(self.ui, 'presetsTableWidget'):
            return
        table = self.ui.presetsTableWidget
        row = table.currentRow()
        if row < 0:
            return
        name_item = table.item(row, 0)
        if not name_item:
            return
        preset_name = name_item.data(Qt.UserRole) or name_item.text()
        preset = self.presetManager.loadPreset(preset_name)
        if preset:
            self.currentPresetName = preset_name
            self.syncPresetEditorWithPresetData(preset)

    def onApplyPresetClicked(self, name):
        table = self.ui.queueTableWidget if hasattr(self.ui, 'queueTableWidget') else None
        if not table:
            return
        selected_rows = table.selectionModel().selectedRows()
        indices = sorted([r.row() for r in selected_rows])
        if not indices:
            QMessageBox.information(self, "Очередь", "Сначала выберите файл(ы) в очереди.")
            return
        preset = self.presetManager.loadPreset(name)
        if not preset:
            QMessageBox.warning(self, "Пресеты", "Не удалось загрузить пресет.")
            return
        for idx in indices:
            if 0 <= idx < len(self.queue):
                item = self.queue[idx]
                item.preset_name = name
                item.setPreset(preset)
                item.command_manually_edited = False
                container = preset.get('container', 'current')
                if container not in ("default", "current", "", None):
                    if item.output_file:
                        base_path = os.path.splitext(item.output_file)[0]
                        item.output_file = base_path + "." + container
                    else:
                        self._generateOutputFileForItem(item)
                elif not item.output_file:
                    self._generateOutputFileForItem(item)
        self.currentPresetName = name
        self.commandManuallyEdited = False
        if hasattr(self, 'codecButtonGroup'):
            self.codecButtonGroup.blockSignals(True)
        if hasattr(self, 'containerButtonGroup'):
            self.containerButtonGroup.blockSignals(True)
        if hasattr(self, 'resolutionButtonGroup'):
            self.resolutionButtonGroup.blockSignals(True)
        self.syncPresetEditorWithPresetData(preset)
        if hasattr(self, 'codecButtonGroup'):
            self.codecButtonGroup.blockSignals(False)
        if hasattr(self, 'containerButtonGroup'):
            self.containerButtonGroup.blockSignals(False)
        if hasattr(self, 'resolutionButtonGroup'):
            self.resolutionButtonGroup.blockSignals(False)
        self.updateQueueTable()
        if len(indices) == 1:
            self.selectedQueueIndex = indices[0]
            if hasattr(self.ui, 'commandDisplay'):
                self.ui.commandDisplay.setReadOnly(False)
            self.updateCommandFromGUI()

    def _getCodecFromButtons(self):
        if hasattr(self.ui, 'codecCurrentButton') and self.ui.codecCurrentButton.isChecked():
            return "current"
        if hasattr(self.ui, 'codecLibx264Button') and self.ui.codecLibx264Button.isChecked():
            return "libx264"
        if hasattr(self.ui, 'codecLibx265Button') and self.ui.codecLibx265Button.isChecked():
            return "libx265"
        if hasattr(self, '_codecProresButton') and self._codecProresButton.isChecked():
            return "prores"
        if hasattr(self.ui, 'codecCustomButton') and self.ui.codecCustomButton.isChecked():
            return self.currentCodecCustom or "current"
        return "current"

    def _getContainerFromButtons(self):
        if hasattr(self.ui, 'containerCurrentButton') and self.ui.containerCurrentButton.isChecked():
            return "current"
        if hasattr(self.ui, 'containerMp4Button') and self.ui.containerMp4Button.isChecked():
            return "mp4"
        if hasattr(self.ui, 'containerMkvButton') and self.ui.containerMkvButton.isChecked():
            return "mkv"
        if hasattr(self, '_containerMovButton') and self._containerMovButton.isChecked():
            return "mov"
        if hasattr(self, '_containerAviButton') and self._containerAviButton.isChecked():
            return "avi"
        if hasattr(self, '_containerMxfButton') and self._containerMxfButton.isChecked():
            return "mxf"
        if hasattr(self.ui, 'containerCustomButton') and self.ui.containerCustomButton.isChecked():
            return self.currentContainerCustom or "current"
        return "current"

    def _getResolutionFromButtons(self):
        if hasattr(self.ui, 'resolutionCurrentButton') and self.ui.resolutionCurrentButton.isChecked():
            return "current"
        if hasattr(self.ui, 'resolution480pButton') and self.ui.resolution480pButton.isChecked():
            return "480p"
        if hasattr(self.ui, 'resolution720pButton') and self.ui.resolution720pButton.isChecked():
            return "720p"
        if hasattr(self.ui, 'resolution1080pButton') and self.ui.resolution1080pButton.isChecked():
            return "1080p"
        if hasattr(self, '_resolution2kButton') and self._resolution2kButton.isChecked():
            return "2k"
        if hasattr(self, '_resolution4kButton') and self._resolution4kButton.isChecked():
            return "4k"
        if hasattr(self.ui, 'resolutionCustomButton') and self.ui.resolutionCustomButton.isChecked():
            return self.currentResolutionCustom or "current"
        return "current"

    def _getAudioCodecFromButtons(self):
        if hasattr(self, '_audioCodecAacButton') and self._audioCodecAacButton.isChecked():
            return "aac"
        if hasattr(self, '_audioCodecMp3Button') and self._audioCodecMp3Button.isChecked():
            return "mp3"
        if hasattr(self, '_audioCodecPcm16Button') and self._audioCodecPcm16Button.isChecked():
            return "pcm_s16le"
        if hasattr(self, '_audioCodecPcm24Button') and self._audioCodecPcm24Button.isChecked():
            return "pcm_s24le"
        if hasattr(self, '_audioCodecCurrentButton') and self._audioCodecCurrentButton.isChecked():
            return "current"
        if hasattr(self, '_audioCodecCustomButton') and self._audioCodecCustomButton.isChecked():
            return self.currentAudioCodecCustom or "aac"
        return "current"

    def onAudioCodecButtonClicked(self, button):
        if hasattr(self, '_audioCodecCustomButton') and button is self._audioCodecCustomButton:
            self._showCustomAudioCodecMenu()
            return
        self.updateCommandFromPresetEditor()

    def syncPresetEditorWithPresetData(self, preset):
        """Устанавливает состояние кнопок редактора по данным пресета."""
        self._suppressPresetEditorUpdates = True
        codec = preset.get("codec", "current")
        container = preset.get("container", "current")
        resolution = preset.get("resolution", "current")

        if codec in ("current", "default"):
            if hasattr(self.ui, 'codecCurrentButton'):
                self.ui.codecCurrentButton.setChecked(True)
        elif codec == "libx264":
            if hasattr(self.ui, 'codecLibx264Button'):
                self.ui.codecLibx264Button.setChecked(True)
        elif codec == "libx265":
            if hasattr(self.ui, 'codecLibx265Button'):
                self.ui.codecLibx265Button.setChecked(True)
        elif codec == "prores" and hasattr(self, '_codecProresButton'):
            self._codecProresButton.setChecked(True)
        elif codec == "copy":
            self.currentCodecCustom = "copy"
            if hasattr(self.ui, 'codecCustomButton'):
                self.ui.codecCustomButton.setChecked(True)
        else:
            self.currentCodecCustom = codec
            if codec and codec not in getattr(self, "customCodecs", []):
                self.customCodecs.append(codec)
                self._saveCustomOptions()
            if hasattr(self.ui, 'codecCustomButton'):
                self.ui.codecCustomButton.setChecked(True)

        if container in ("current", "default", ""):
            if hasattr(self.ui, 'containerCurrentButton'):
                self.ui.containerCurrentButton.setChecked(True)
        elif container == "mp4":
            if hasattr(self.ui, 'containerMp4Button'):
                self.ui.containerMp4Button.setChecked(True)
        elif container == "mkv":
            if hasattr(self.ui, 'containerMkvButton'):
                self.ui.containerMkvButton.setChecked(True)
        elif container == "mov" and hasattr(self, '_containerMovButton'):
            self._containerMovButton.setChecked(True)
        elif container == "avi" and hasattr(self, '_containerAviButton'):
            self._containerAviButton.setChecked(True)
        elif container == "mxf" and hasattr(self, '_containerMxfButton'):
            self._containerMxfButton.setChecked(True)
        else:
            self.currentContainerCustom = container
            if container and container not in getattr(self, "customContainers", []):
                self.customContainers.append(container)
                self._saveCustomOptions()
            if hasattr(self.ui, 'containerCustomButton'):
                self.ui.containerCustomButton.setChecked(True)

        if resolution in ("current", "default", ""):
            if hasattr(self.ui, 'resolutionCurrentButton'):
                self.ui.resolutionCurrentButton.setChecked(True)
        elif resolution == "480p":
            if hasattr(self.ui, 'resolution480pButton'):
                self.ui.resolution480pButton.setChecked(True)
        elif resolution == "720p":
            if hasattr(self.ui, 'resolution720pButton'):
                self.ui.resolution720pButton.setChecked(True)
        elif resolution == "1080p":
            if hasattr(self.ui, 'resolution1080pButton'):
                self.ui.resolution1080pButton.setChecked(True)
        elif resolution == "2k" and hasattr(self, '_resolution2kButton'):
            self._resolution2kButton.setChecked(True)
        elif resolution == "4k" and hasattr(self, '_resolution4kButton'):
            self._resolution4kButton.setChecked(True)
        else:
            self.currentResolutionCustom = resolution
            res_norm = (self.currentResolutionCustom or "").replace("x", ":")
            if res_norm and res_norm not in getattr(self, "customResolutions", []):
                self.customResolutions.append(res_norm)
                self._saveCustomOptions()
            if hasattr(self.ui, 'resolutionCustomButton'):
                self.ui.resolutionCustomButton.setChecked(True)

        audio = preset.get("audio_codec", "current")
        if audio == "aac" and hasattr(self, '_audioCodecAacButton'):
            self._audioCodecAacButton.setChecked(True)
        elif audio == "mp3" and hasattr(self, '_audioCodecMp3Button'):
            self._audioCodecMp3Button.setChecked(True)
        elif audio == "pcm_s16le" and hasattr(self, '_audioCodecPcm16Button'):
            self._audioCodecPcm16Button.setChecked(True)
        elif audio == "pcm_s24le" and hasattr(self, '_audioCodecPcm24Button'):
            self._audioCodecPcm24Button.setChecked(True)
        elif audio in ("current", "copy") and hasattr(self, '_audioCodecCurrentButton'):
            self._audioCodecCurrentButton.setChecked(True)
        elif hasattr(self, '_audioCodecCustomButton'):
            self.currentAudioCodecCustom = audio if audio not in ("aac", "mp3", "pcm_s16le", "pcm_s24le", "current") else (self.currentAudioCodecCustom or "aac")
            if self.currentAudioCodecCustom and self.currentAudioCodecCustom not in getattr(self, "customAudioCodecs", []):
                self.customAudioCodecs.append(self.currentAudioCodecCustom)
                self._saveCustomOptions()
            self._audioCodecCustomButton.setChecked(True)

        if hasattr(self, '_crfSpin'):
            self._crfSpin.setValue(int(preset.get("crf", 0) or 0))
        if hasattr(self, '_bitrateSpin'):
            self._bitrateSpin.setValue(int(preset.get("bitrate", 0) or 0))
        if hasattr(self, '_fpsSpin'):
            self._fpsSpin.setValue(int(preset.get("fps", 0) or 0))
        if hasattr(self, '_audioBitrateSpin'):
            self._audioBitrateSpin.setValue(int(preset.get("audio_bitrate", 0) or 0))
        if hasattr(self, '_sampleRateSpin'):
            self._sampleRateSpin.setValue(int(preset.get("sample_rate", 0) or 0))
        if hasattr(self, '_keyintSpin'):
            self._keyintSpin.setValue(int(preset.get("keyint", 0) or 0))
        if hasattr(self, '_presetCombo'):
            idx = self._presetCombo.findText(preset.get("preset_speed", "medium") or "medium")
            if idx >= 0:
                self._presetCombo.setCurrentIndex(idx)
        if hasattr(self, '_profileLevelEdit'):
            self._profileLevelEdit.setText(preset.get("profile_level", "") or "")
        if hasattr(self, '_pixelFormatEdit'):
            self._pixelFormatEdit.setText(preset.get("pixel_format", "") or "")
        if hasattr(self, '_tuneEdit'):
            self._tuneEdit.setText(preset.get("tune", "") or "")
        if hasattr(self, '_threadsSpin'):
            self._threadsSpin.setValue(int(preset.get("threads", 0) or 0))
        if hasattr(self, '_checkTagHvc1'):
            v = preset.get("tag_hvc1", False)
            self._checkTagHvc1.setChecked(v is True or str(v).strip() == "1")
        if hasattr(self, '_checkVfLanczos'):
            v = preset.get("vf_lanczos", False)
            self._checkVfLanczos.setChecked(v is True or str(v).strip() == "1")
        self._suppressPresetEditorUpdates = False
        self._updateConflictWarningsFromEditor()

    def syncPresetEditorWithQueueItem(self, item: QueueItem):
        preset_data = {
            "codec": item.codec,
            "container": item.container,
            "resolution": item.resolution,
            "audio_codec": getattr(item, "audio_codec", "current"),
            "crf": getattr(item, "crf", 0),
            "bitrate": getattr(item, "bitrate", 0),
            "fps": getattr(item, "fps", 0),
            "audio_bitrate": getattr(item, "audio_bitrate", 0),
            "sample_rate": getattr(item, "sample_rate", 0),
            "preset_speed": getattr(item, "preset_speed", "medium"),
            "profile_level": getattr(item, "profile_level", ""),
            "pixel_format": getattr(item, "pixel_format", ""),
            "tune": getattr(item, "tune", ""),
            "threads": getattr(item, "threads", 0),
            "keyint": getattr(item, "keyint", False),
            "tag_hvc1": getattr(item, "tag_hvc1", False),
            "vf_lanczos": getattr(item, "vf_lanczos", False),
        }
        self.currentPresetName = item.preset_name
        self.syncPresetEditorWithPresetData(preset_data)

    def onCodecButtonClicked(self, button):
        if hasattr(self.ui, 'codecCustomButton') and button is self.ui.codecCustomButton:
            self._showCustomCodecMenu()
            return
        self.updateCommandFromPresetEditor()

    def onContainerButtonClicked(self, button):
        if hasattr(self.ui, 'containerCustomButton') and button is self.ui.containerCustomButton:
            self._showCustomContainerMenu()
            return
        self.updateCommandFromPresetEditor()

    def onResolutionButtonClicked(self, button):
        if hasattr(self.ui, 'resolutionCustomButton') and button is self.ui.resolutionCustomButton:
            self._showCustomResolutionMenu()
            return
        self.updateCommandFromPresetEditor()

    def updateCommandFromPresetEditor(self):
        """Обновляет команду FFmpeg на основе текущих настроек редактора пресетов."""
        if getattr(self, "_suppressPresetEditorUpdates", False):
            return
        table = self.ui.queueTableWidget if hasattr(self.ui, 'queueTableWidget') else None
        if not table:
            return
        selected_rows = table.selectionModel().selectedRows()
        indices = sorted([r.row() for r in selected_rows])
        if not indices:
            return

        codec = self._getCodecFromButtons()
        container = self._getContainerFromButtons()
        resolution = self._getResolutionFromButtons()
        audio_codec = self._getAudioCodecFromButtons()
        crf = self._crfSpin.value() if hasattr(self, '_crfSpin') else 0
        bitrate = self._bitrateSpin.value() if hasattr(self, '_bitrateSpin') else 0
        fps = self._fpsSpin.value() if hasattr(self, '_fpsSpin') else 0
        audio_bitrate = self._audioBitrateSpin.value() if hasattr(self, '_audioBitrateSpin') else 0
        sample_rate = self._sampleRateSpin.value() if hasattr(self, '_sampleRateSpin') else 0
        preset_speed = self._presetCombo.currentText() if hasattr(self, '_presetCombo') else "medium"
        profile_level = self._profileLevelEdit.text().strip() if hasattr(self, '_profileLevelEdit') else ""
        pixel_format = self._pixelFormatEdit.text().strip() if hasattr(self, '_pixelFormatEdit') else ""
        tune = self._tuneEdit.text().strip() if hasattr(self, '_tuneEdit') else ""
        threads = self._threadsSpin.value() if hasattr(self, '_threadsSpin') else 0
        keyint = self._keyintSpin.value() if hasattr(self, '_keyintSpin') else 0
        tag_hvc1 = self._checkTagHvc1.isChecked() if hasattr(self, '_checkTagHvc1') else False
        vf_lanczos = self._checkVfLanczos.isChecked() if hasattr(self, '_checkVfLanczos') else False

        default_like = ("default", "current", "")
        warned_copy = False
        for idx in indices:
            if 0 <= idx < len(self.queue):
                item = self.queue[idx]
                item.codec = codec
                item.container = container
                item.resolution = resolution
                item.audio_codec = audio_codec
                item.crf = crf
                item.bitrate = bitrate
                item.fps = fps
                item.audio_bitrate = audio_bitrate
                item.sample_rate = sample_rate
                item.preset_speed = preset_speed
                item.profile_level = profile_level
                item.pixel_format = pixel_format
                item.tune = tune
                item.threads = threads
                item.keyint = int(keyint)
                item.tag_hvc1 = tag_hvc1
                item.vf_lanczos = vf_lanczos

                if not warned_copy:
                    if codec == "copy" and (vf_lanczos or resolution not in default_like or crf or bitrate or fps or preset_speed or profile_level or pixel_format or tune or threads or keyint):
                        if hasattr(self, "updateStatus"):
                            self.updateStatus("Внимание: при copy видео фильтры/CRF/bitrate/FPS игнорируются.")
                        warned_copy = True
                    if audio_codec == "current" and (audio_bitrate or sample_rate):
                        if hasattr(self, "updateStatus"):
                            self.updateStatus("Внимание: при copy аудио битрейт/частота игнорируются.")
                        warned_copy = True

                if resolution == "custom":
                    item.custom_resolution = self.currentResolutionCustom
                else:
                    item.custom_resolution = ""

                if container not in ("default", "current", ""):
                    if item.output_file:
                        base_path = os.path.splitext(item.output_file)[0]
                        item.output_file = base_path + "." + container
                    else:
                        self._generateOutputFileForItem(item)
                elif not item.output_file:
                    self._generateOutputFileForItem(item)

                if isinstance(item.preset_name, str) and item.preset_name.startswith("cmd:"):
                    self._applyPathsToSavedCommand(item)

                if isinstance(item.preset_name, str) and item.preset_name.startswith("cmd:"):
                    pass
                elif item.preset_name and item.preset_name not in ("default", "custom"):
                    applied = self.presetManager.loadPreset(item.preset_name)
                    if applied and self._presetMatchesItem(applied, item):
                        pass
                    else:
                        item.preset_name = "custom"
                else:
                    default_audio = ("current", "", "default")
                    if (codec in default_like and container in default_like and resolution in default_like and audio_codec in default_audio):
                        item.preset_name = "default"
                    else:
                        item.preset_name = "custom"

        self.commandManuallyEdited = False
        self.updateQueueTable()
        if len(indices) == 1 and hasattr(self.ui, "commandDisplay"):
            self.updateCommandFromGUI()
        self._updateConflictWarningsFromEditor()

    def _presetMatchesItem(self, preset, item):
        def b(v):
            return (v is True) or (str(v).strip() == "1")
        return (
            (preset.get("codec", "default") or "default") == (item.codec or "default") and
            (preset.get("container", "default") or "default") == (item.container or "default") and
            (preset.get("resolution", "default") or "default") == (item.resolution or "default") and
            (preset.get("audio_codec", "current") or "current") == (item.audio_codec or "current") and
            int(preset.get("crf", 0) or 0) == int(item.crf or 0) and
            int(preset.get("bitrate", 0) or 0) == int(item.bitrate or 0) and
            int(preset.get("fps", 0) or 0) == int(item.fps or 0) and
            int(preset.get("audio_bitrate", 0) or 0) == int(item.audio_bitrate or 0) and
            int(preset.get("sample_rate", 0) or 0) == int(item.sample_rate or 0) and
            (preset.get("preset_speed", "medium") or "medium") == (item.preset_speed or "medium") and
            (preset.get("profile_level", "") or "") == (item.profile_level or "") and
            (preset.get("pixel_format", "") or "") == (item.pixel_format or "") and
            (preset.get("tune", "") or "") == (item.tune or "") and
            int(preset.get("threads", 0) or 0) == int(item.threads or 0) and
            int(preset.get("keyint", 0) or 0) == int(item.keyint or 0) and
            b(preset.get("tag_hvc1", False)) == bool(item.tag_hvc1) and
            b(preset.get("vf_lanczos", False)) == bool(item.vf_lanczos) and
            (preset.get("extra_args", "") or "") == (item.extra_args or "")
        )

    def _getContainerExtForWarnings(self, container_value):
        if container_value in ("default", "current", "", None):
            item = self.getSelectedQueueItem()
            if item and item.file_path:
                return os.path.splitext(item.file_path)[1].lstrip(".").lower()
            return ""
        return str(container_value).lower()

    def _isTagHvc1Applicable(self, codec, container_ext):
        return container_ext in ("mp4", "mov", "m4v") and (codec in ("libx265", "hevc", "h265", "copy"))

    def _setWidgetConflict(self, widget, on):
        if not widget:
            return
        if on:
            if widget not in self._conflictStyles:
                self._conflictStyles[widget] = widget.styleSheet()
            widget.setStyleSheet(self._conflictStyles[widget] + " border:1px solid #ff5555;")
        else:
            if widget in self._conflictStyles:
                widget.setStyleSheet(self._conflictStyles.pop(widget))

    def _clearAllConflicts(self):
        for w in list(self._conflictStyles.keys()):
            self._setWidgetConflict(w, False)

    def _updateConflictWarningsFromEditor(self):
        if self._warningLabel is None:
            return
        codec = self._getCodecFromButtons()
        container = self._getContainerFromButtons()
        resolution = self._getResolutionFromButtons()
        audio_codec = self._getAudioCodecFromButtons()
        crf = self._crfSpin.value() if hasattr(self, "_crfSpin") else 0
        bitrate = self._bitrateSpin.value() if hasattr(self, "_bitrateSpin") else 0
        fps = self._fpsSpin.value() if hasattr(self, "_fpsSpin") else 0
        audio_bitrate = self._audioBitrateSpin.value() if hasattr(self, "_audioBitrateSpin") else 0
        sample_rate = self._sampleRateSpin.value() if hasattr(self, "_sampleRateSpin") else 0
        preset_speed = self._presetCombo.currentText() if hasattr(self, "_presetCombo") else ""
        profile_level = self._profileLevelEdit.text().strip() if hasattr(self, "_profileLevelEdit") else ""
        pixel_format = self._pixelFormatEdit.text().strip() if hasattr(self, "_pixelFormatEdit") else ""
        tune = self._tuneEdit.text().strip() if hasattr(self, "_tuneEdit") else ""
        threads = self._threadsSpin.value() if hasattr(self, "_threadsSpin") else 0
        keyint = self._keyintSpin.value() if hasattr(self, "_keyintSpin") else 0
        tag_hvc1 = self._checkTagHvc1.isChecked() if hasattr(self, "_checkTagHvc1") else False
        vf_lanczos = self._checkVfLanczos.isChecked() if hasattr(self, "_checkVfLanczos") else False

        container_ext = self._getContainerExtForWarnings(container)
        apply_tag = self._isTagHvc1Applicable(codec, container_ext)

        copy_video_conflict = (codec == "copy") and (
            vf_lanczos or resolution not in ("current", "default", "") or
            crf > 0 or bitrate > 0 or fps > 0 or preset_speed or profile_level or
            pixel_format or tune or threads > 0 or keyint > 0
        )
        copy_audio_conflict = (audio_codec in ("current", "copy")) and (audio_bitrate > 0 or sample_rate > 0)
        tag_conflict = tag_hvc1 and not apply_tag

        warnings = []
        self._clearAllConflicts()

        if tag_conflict:
            warnings.append("tag hvc1 будет проигнорирован: поддерживается только HEVC в MP4/MOV/M4V.")
            self._setWidgetConflict(self._checkTagHvc1, True)
        if copy_video_conflict:
            warnings.append("Copy видео: фильтры/CRF/битрейт/FPS/preset/keyint игнорируются.")
            for w in (self._checkVfLanczos, self._crfSpin, self._bitrateSpin, self._fpsSpin,
                      self._presetCombo, self._profileLevelEdit, self._pixelFormatEdit, self._tuneEdit,
                      self._threadsSpin, self._keyintSpin):
                self._setWidgetConflict(w, True)
        if copy_audio_conflict:
            warnings.append("Copy аудио: битрейт/частота игнорируются.")
            for w in (self._audioBitrateSpin, self._sampleRateSpin):
                self._setWidgetConflict(w, True)

        item = self.getSelectedQueueItem()
        segments = self._getTrimSegments(item) if item else []
        if len(segments) > 1:
            has_audio = getattr(item, "has_audio", None)
            if has_audio is False:
                warnings.append("Склейка: у файла нет аудио, звук в результате отсутствует.")
            else:
                warnings.append("Склейка: аудио перекодируется в AAC, выбор аудиокодека игнорируется.")

        if warnings:
            self._warningLabel.setText(" | ".join(warnings))
            self._warningLabel.show()
        else:
            self._warningLabel.hide()

        if self._extraLabel is not None:
            name = self.currentPresetName or ""
            extra_text = ""
            if name and name not in ("default", "custom") and not name.startswith("cmd:"):
                preset = self.presetManager.loadPreset(name)
                extra_text = (preset or {}).get("extra_args", "") or ""
            if extra_text.strip():
                self._extraLabel.setText(f"Extra параметры пресета: {extra_text}")
                self._extraLabel.show()
            else:
                self._extraLabel.hide()

    def _getPresetExtraFromUI(self):
        def spin_val(attr, default=0):
            w = getattr(self, attr, None)
            return w.value() if w is not None else default
        def text_val(attr, default=""):
            w = getattr(self, attr, None)
            return w.text().strip() if w is not None else default
        def combo_text(attr, default=""):
            w = getattr(self, attr, None)
            return w.currentText() if w is not None else default
        def check_val(attr, default=False):
            w = getattr(self, attr, None)
            return w.isChecked() if w is not None else default
        return {
            "audio_codec": self._getAudioCodecFromButtons(),
            "crf": spin_val("_crfSpin"),
            "bitrate": spin_val("_bitrateSpin"),
            "fps": spin_val("_fpsSpin"),
            "audio_bitrate": spin_val("_audioBitrateSpin"),
            "sample_rate": spin_val("_sampleRateSpin"),
            "preset_speed": combo_text("_presetCombo", "medium"),
            "profile_level": text_val("_profileLevelEdit"),
            "pixel_format": text_val("_pixelFormatEdit"),
            "tune": text_val("_tuneEdit"),
            "threads": spin_val("_threadsSpin"),
            "keyint": spin_val("_keyintSpin"),
            "tag_hvc1": check_val("_checkTagHvc1"),
            "vf_lanczos": check_val("_checkVfLanczos"),
        }

    def _generateCommandWithoutExtra(self):
        item = self.getSelectedQueueItem()
        if not item:
            return ""
        saved_extra = getattr(item, "extra_args", "")
        item.extra_args = ""
        cmd = self.generateFFmpegCommand()
        item.extra_args = saved_extra
        return cmd

    def createPreset(self):
        codec = self._getCodecFromButtons()
        container = self._getContainerFromButtons()
        resolution = self._getResolutionFromButtons()
        name, ok = QInputDialog.getText(self, "Создать пресет", "Имя пресета:")
        if not ok or not name.strip():
            return
        name = name.strip()
        desc, ok = QInputDialog.getMultiLineText(self, "Описание пресета", "Описание (необязательно):")
        if not ok:
            return
        extra = self._getPresetExtraFromUI()
        if not self.presetManager.savePreset(name, codec, resolution, container, desc.strip(), insert_at_top=True, **extra):
            QMessageBox.warning(self, "Ошибка сохранения", f"Не удалось сохранить {CONFIG_PRESETS_XML}. Проверьте права на запись в папке приложения.")
            return
        self.currentPresetName = name
        self.refreshPresetsTable()

    def saveCurrentPreset(self):
        codec = self._getCodecFromButtons()
        container = self._getContainerFromButtons()
        resolution = self._getResolutionFromButtons()
        name = self.currentPresetName
        if not name or name == "custom":
            name, ok = QInputDialog.getText(self, "Сохранить пресет", "Имя пресета:")
            if not ok or not name.strip():
                return
            name = name.strip()
        desc = ""
        existing = self.presetManager.loadPreset(name)
        if existing and existing.get("description"):
            desc = existing["description"]
        extra = self._getPresetExtraFromUI()
        if not self.presetManager.savePreset(name, codec, resolution, container, desc, **extra):
            QMessageBox.warning(self, "Ошибка сохранения", f"Не удалось сохранить {CONFIG_PRESETS_XML}. Проверьте права на запись в папке приложения.")
            return
        self.currentPresetName = name
        self.refreshPresetsTable()

    def savePresetWithCustomParams(self):
        item = self.getSelectedQueueItem()
        if not item:
            QMessageBox.information(self, "Сохранить пресет", "Сначала выберите файл в очереди.")
            return
        if not hasattr(self.ui, "commandDisplay"):
            return
        user_cmd = self.ui.commandDisplay.toPlainText().strip()
        if not user_cmd or user_cmd.lower() == "ffmpeg":
            QMessageBox.information(self, "Сохранить пресет", "Команда пуста. Сначала задайте параметры или отредактируйте команду.")
            return
        base_cmd = self._generateCommandWithoutExtra()
        extra_args_list = self._extractExtraArgsFromCommands(base_cmd, user_cmd)
        extra_args = " ".join(extra_args_list).strip()
        codec = self._getCodecFromButtons()
        container = self._getContainerFromButtons()
        resolution = self._getResolutionFromButtons()
        name = self.currentPresetName
        if not name or name == "custom":
            name, ok = QInputDialog.getText(self, "Сохранить пресет", "Имя пресета:")
            if not ok or not name.strip():
                return
            name = name.strip()
        desc = ""
        existing = self.presetManager.loadPreset(name)
        if existing and existing.get("description"):
            desc = existing["description"]
        extra = self._getPresetExtraFromUI()
        extra["extra_args"] = extra_args
        if not self.presetManager.savePreset(name, codec, resolution, container, desc, **extra):
            QMessageBox.warning(self, "Ошибка сохранения", f"Не удалось сохранить {CONFIG_PRESETS_XML}. Проверьте права на запись в папке приложения.")
            return
        self.currentPresetName = name
        self.refreshPresetsTable()
        QMessageBox.information(self, "Сохранено", "Пресет сохранён с дополнительными параметрами.")

    def _chooseDataType(self, title):
        items = ["Пресеты", "Команды FFmpeg", "Кастомные параметры"]
        choice, ok = QInputDialog.getItem(self, title, "Что импортировать/экспортировать:", items, 0, False)
        if not ok or not choice:
            return None
        if choice == "Пресеты":
            return "presets"
        if choice == "Команды FFmpeg":
            return "commands"
        return "custom"

    def exportData(self):
        dtype = self._chooseDataType("Экспорт")
        if not dtype:
            return
        if dtype == "presets":
            source = self.presetManager.presets_file
            filter_str = "XML файлы (*.xml)"
        elif dtype == "commands":
            source = self._savedCommandsPath
            filter_str = "JSON файлы (*.json)"
        else:
            source = self._customOptionsPath
            filter_str = "JSON файлы (*.json)"
        if not os.path.exists(source):
            QMessageBox.information(self, "Экспорт", "Файл не найден. Сначала создайте данные в программе.")
            return
        default_name = os.path.basename(source)
        file_path, _ = QFileDialog.getSaveFileName(self, "Экспорт", default_name, filter_str)
        if not file_path:
            return
        try:
            shutil.copyfile(source, file_path)
            QMessageBox.information(self, "Экспорт", f"Файл сохранён:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Экспорт", f"Не удалось сохранить файл:\n{str(e)}")

    def importData(self):
        dtype = self._chooseDataType("Импорт")
        if not dtype:
            return
        if dtype == "presets":
            file_path, _ = QFileDialog.getOpenFileName(self, "Импорт пресетов", "", "XML файлы (*.xml)")
            if not file_path:
                return
            ok = self.presetManager.mergePresetsFromFile(file_path)
            if ok:
                QMessageBox.information(self, "Импорт", "Пресеты импортированы (слияние выполнено).")
                self.refreshPresetsTable()
            else:
                QMessageBox.critical(self, "Импорт", "Не удалось импортировать пресеты.")
            return
        if dtype == "commands":
            file_path, _ = QFileDialog.getOpenFileName(self, "Импорт команд", "", "JSON файлы (*.json)")
            if not file_path:
                return
            ok = self._mergeSavedCommandsFromFile(file_path)
            if ok:
                QMessageBox.information(self, "Импорт", "Команды импортированы.")
            else:
                QMessageBox.critical(self, "Импорт", "Не удалось импортировать команды.")
            return
        file_path, _ = QFileDialog.getOpenFileName(self, "Импорт пользовательских параметров", "", "JSON файлы (*.json)")
        if not file_path:
            return
        ok = self._mergeCustomOptionsFromFile(file_path)
        if ok:
            QMessageBox.information(self, "Импорт", "Параметры импортированы.")
        else:
            QMessageBox.critical(self, "Импорт", "Не удалось импортировать параметры.")

    def _mergeSavedCommandsFromFile(self, file_path):
        try:
            with open(file_path, "r", encoding=JSON_ENCODING) as f:
                data = json.load(f)
            incoming = data.get("commands", [])
            if not isinstance(incoming, list):
                return False
            existing = self._loadSavedCommands()
            names = {c.get("name") for c in existing}
            for cmd in incoming:
                if not isinstance(cmd, dict):
                    continue
                name = cmd.get("name")
                command = cmd.get("command")
                if not name or command is None:
                    continue
                if name in names:
                    continue
                existing.append({"name": name, "command": command})
                names.add(name)
            self._saveSavedCommands(existing)
            return True
        except Exception:
            return False

    def _mergeCustomOptionsFromFile(self, file_path):
        try:
            with open(file_path, "r", encoding=JSON_ENCODING) as f:
                data = json.load(f)
            containers = data.get("containers", [])
            codecs = data.get("codecs", [])
            resolutions = data.get("resolutions", [])
            audio_codecs = data.get("audio_codecs", [])
            if not isinstance(containers, list):
                containers = []
            if not isinstance(codecs, list):
                codecs = []
            if not isinstance(resolutions, list):
                resolutions = []
            if not isinstance(audio_codecs, list):
                audio_codecs = []
            self.customContainers = list(dict.fromkeys(self.customContainers + containers))
            self.customCodecs = list(dict.fromkeys(self.customCodecs + codecs))
            self.customResolutions = list(dict.fromkeys(self.customResolutions + resolutions))
            self.customAudioCodecs = list(dict.fromkeys(self.customAudioCodecs + audio_codecs))
            self._saveCustomOptions()
            return True
        except Exception:
            return False

    def saveCurrentCommand(self):
        cmd = self.ui.commandDisplay.toPlainText().strip() if hasattr(self.ui, "commandDisplay") else ""
        if not cmd or cmd.lower() == "ffmpeg":
            QMessageBox.information(self, "Сохранение команды", "Введите команду в поле выше или сгенерируйте её, выбрав файл и пресет.")
            return
        name, ok = QInputDialog.getText(self, "Сохранить команду", "Введите имя для сохранённой команды:", text="")
        if not ok or not name.strip():
            return
        name = name.strip()
        commands = self._loadSavedCommands()
        commands = [c for c in commands if c.get("name") != name]
        commands.append({"name": name, "command": cmd})
        self._saveSavedCommands(commands)
        QMessageBox.information(self, "Сохранено", f'Команда «{name}» сохранена.')

    def loadSavedCommand(self):
        item = self.getSelectedQueueItem()
        if not item:
            QMessageBox.information(self, "Загрузить команду", "Сначала выберите файл в очереди.")
            return
        commands = self._loadSavedCommands()
        if not commands:
            QMessageBox.information(self, "Загрузить команду", "Нет сохранённых команд. Сохраните команду кнопкой «Сохранить команду».")
            return
        names = [c.get("name", "") for c in commands]
        name, ok = QInputDialog.getItem(self, "Загрузить команду", "Выберите сохранённую команду:", names, 0, False)
        if not ok or not name:
            return
        entry = next((c for c in commands if c.get("name") == name), None)
        if not entry:
            return
        cmd = entry.get("command", "").strip()
        if not cmd:
            return
        item.preset_name = f"cmd:{name}"
        item.command = cmd
        item.command_manually_edited = True
        item.last_generated_command = getattr(item, "last_generated_command", "") or ""
        self.commandManuallyEdited = True
        if hasattr(self.ui, "commandDisplay"):
            self._applyPathsToSavedCommand(item, update_display=True)
            self.ui.commandDisplay.setReadOnly(False)
        self.updateQueueTable()
        QMessageBox.information(self, "Загружено", f'Команда «{name}» применена к выбранному файлу. При кодировании будут подставлены пути этого файла.')

    def deleteSavedCommand(self):
        commands = self._loadSavedCommands()
        if not commands:
            QMessageBox.information(self, "Удалить команду", "Нет сохранённых команд.")
            return
        names = [c.get("name", "") for c in commands]
        name, ok = QInputDialog.getItem(self, "Удалить команду", "Выберите команду для удаления:", names, 0, False)
        if not ok or not name:
            return
        commands = [c for c in commands if c.get("name") != name]
        self._saveSavedCommands(commands)
        QMessageBox.information(self, "Удалено", f'Команда «{name}» удалена из списка сохранённых.')
