import xml.etree.ElementTree as ET
import os
import logging

from constants import CONFIG_PRESETS_XML

logger = logging.getLogger(__name__)

# Ключи пресета (кроме name) и значения по умолчанию — единый источник для loadPreset/loadAllPresets/mergePresetsFromFile
PRESET_EXTRA_KEYS = (
    'audio_codec', 'crf', 'bitrate', 'fps', 'audio_bitrate', 'sample_rate',
    'preset_speed', 'profile_level', 'pixel_format', 'tune', 'threads',
    'keyint', 'tag_hvc1', 'vf_lanczos', 'extra_args'
)
PRESET_ALL_KEYS = ('codec', 'resolution', 'container', 'description', 'audio_codec',
                   'crf', 'bitrate', 'fps', 'audio_bitrate', 'sample_rate', 'preset_speed',
                   'profile_level', 'pixel_format', 'tune', 'threads', 'keyint', 'tag_hvc1', 'vf_lanczos', 'extra_args')
PRESET_DEFAULTS = {
    "description": "", "profile_level": "", "pixel_format": "", "tune": "",
    "crf": "0", "bitrate": "0", "fps": "0", "audio_bitrate": "0", "sample_rate": "0",
    "threads": "0", "keyint": "0", "tag_hvc1": "0", "vf_lanczos": "0",
    "preset_speed": "medium", "audio_codec": "", "extra_args": "", "codec": "", "resolution": "", "container": "",
}


class PresetManager:
    """Работа с presets.xml."""
    def __init__(self):
        self.presets_file = os.path.join(os.path.dirname(__file__), CONFIG_PRESETS_XML)

    def savePreset(self, name, codec, resolution, container, description="", insert_at_top=False, **kwargs):
        """Сохраняет пресет. Существующий сохраняет позицию, новый можно вставить в начало.
        Доп. параметры: audio_codec, crf, bitrate, fps, audio_bitrate, sample_rate, preset_speed,
        profile_level, pixel_format, tune, threads, keyint, tag_hvc1, vf_lanczos, extra_args.
        """
        try:
            if os.path.exists(self.presets_file):
                tree = ET.parse(self.presets_file)
                root = tree.getroot()
            else:
                root = ET.Element('presets')
                tree = ET.ElementTree(root)

            preset_elem = None
            for preset in list(root):
                if preset.get('name') == name:
                    preset_elem = preset
                    break

            if preset_elem is None:
                preset_elem = ET.Element('preset')
                if insert_at_top:
                    root.insert(0, preset_elem)
                else:
                    root.append(preset_elem)
            else:
                for child in list(preset_elem):
                    preset_elem.remove(child)
            preset_elem.set('name', name)
            ET.SubElement(preset_elem, 'codec').text = codec or ""
            ET.SubElement(preset_elem, 'resolution').text = resolution or ""
            ET.SubElement(preset_elem, 'container').text = container or ""
            desc_elem = ET.SubElement(preset_elem, 'description')
            desc_elem.text = description if description else ""

            for key in PRESET_EXTRA_KEYS:
                val = kwargs.get(key)
                if val is None:
                    continue
                if isinstance(val, bool):
                    val = "1" if val else "0"
                else:
                    val = str(val)
                ET.SubElement(preset_elem, key).text = val

            tree.write(self.presets_file, encoding='utf-8', xml_declaration=True)
            return True
        except Exception:
            logger.exception("Ошибка сохранения пресета")
            return False

    def removePreset(self, name):
        if not os.path.exists(self.presets_file):
            return
        tree = ET.parse(self.presets_file)
        root = tree.getroot()
        for preset in list(root):
            if preset.get('name') == name:
                root.remove(preset)
        tree.write(self.presets_file, encoding='utf-8', xml_declaration=True)

    def movePreset(self, name, direction):
        """Перемещает пресет вверх/вниз в списке. direction: 'up' или 'down'."""
        if not os.path.exists(self.presets_file):
            return False
        tree = ET.parse(self.presets_file)
        root = tree.getroot()
        presets = list(root)
        idx = None
        for i, p in enumerate(presets):
            if p.get("name") == name:
                idx = i
                break
        if idx is None:
            return False
        if direction == "up" and idx > 0:
            presets[idx - 1], presets[idx] = presets[idx], presets[idx - 1]
        elif direction == "down" and idx < len(presets) - 1:
            presets[idx + 1], presets[idx] = presets[idx], presets[idx + 1]
        else:
            return False
        # Пересобираем root в новом порядке
        for p in list(root):
            root.remove(p)
        for p in presets:
            root.append(p)
        tree.write(self.presets_file, encoding='utf-8', xml_declaration=True)
        return True

    def _elem_text(self, elem, default=""):
        if elem is None or elem.text is None:
            return default
        return elem.text

    def _preset_from_elem(self, preset_elem):
        """Собирает словарь данных пресета из XML-элемента. Использует PRESET_ALL_KEYS и PRESET_DEFAULTS."""
        data = {"name": preset_elem.get("name", "")}
        for key in PRESET_ALL_KEYS:
            data[key] = self._elem_text(preset_elem.find(key), PRESET_DEFAULTS.get(key, ""))
        return data

    def loadPreset(self, name):
        result = {}
        if not os.path.exists(self.presets_file):
            return result
        tree = ET.parse(self.presets_file)
        root = tree.getroot()
        for preset in root:
            if preset.get('name') == name:
                return self._preset_from_elem(preset)
        return result

    def loadAllPresets(self):
        """Возвращает список словарей с данными по всем пресетам (включая все доп. поля)."""
        presets = []
        if not os.path.exists(self.presets_file):
            return presets
        tree = ET.parse(self.presets_file)
        root = tree.getroot()
        for preset in root:
            presets.append(self._preset_from_elem(preset))
        return presets

    def mergePresetsFromFile(self, file_path):
        """Импортирует пресеты из файла, не перезаписывая существующие.
        При совпадении имени добавляет суффикс ' imported'.
        """
        if not os.path.exists(file_path):
            return False
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            presets = []
            if root.tag == "presets":
                presets = list(root)
            elif root.tag == "preset":
                presets = [root]
            else:
                return False
            existing_names = {p.get("name", "") for p in self.loadAllPresets()}
            for preset in presets:
                name = preset.get("name", "")
                if not name:
                    continue
                incoming = self._preset_from_elem(preset)
                incoming["name"] = name
                new_name = name
                if new_name in existing_names:
                    suffix = " imported"
                    new_name = f"{name}{suffix}"
                    counter = 2
                    while new_name in existing_names:
                        new_name = f"{name}{suffix} {counter}"
                        counter += 1
                self.savePreset(
                    new_name,
                    incoming["codec"],
                    incoming["resolution"],
                    incoming["container"],
                    incoming["description"],
                    **{k: incoming[k] for k in incoming if k not in ("name", "codec", "resolution", "container", "description")}
                )
                existing_names.add(new_name)
            return True
        except Exception:
            return False
