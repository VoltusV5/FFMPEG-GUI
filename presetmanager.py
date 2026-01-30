import xml.etree.ElementTree as ET
import os

class PresetManager:
    def __init__(self):
        # Путь к presets.xml рядом с exe или скриптом
        self.presets_file = os.path.join(os.path.dirname(__file__), 'presets.xml')

    def savePreset(self, name, codec, resolution, container, description="", **kwargs):
        """Сохраняет пресет. Доп. параметры: audio_codec, crf, bitrate, fps, audio_bitrate, sample_rate, preset_speed, profile_level, pixel_format, tune, threads, keyint, tag_hvc1, vf_lanczos."""
        if os.path.exists(self.presets_file):
            tree = ET.parse(self.presets_file)
            root = tree.getroot()
        else:
            root = ET.Element('presets')
            tree = ET.ElementTree(root)

        for preset in list(root):
            if preset.get('name') == name:
                root.remove(preset)

        preset_elem = ET.SubElement(root, 'preset')
        preset_elem.set('name', name)
        ET.SubElement(preset_elem, 'codec').text = codec or ""
        ET.SubElement(preset_elem, 'resolution').text = resolution or ""
        ET.SubElement(preset_elem, 'container').text = container or ""
        desc_elem = ET.SubElement(preset_elem, 'description')
        desc_elem.text = description if description else ""

        extra_keys = (
            'audio_codec', 'crf', 'bitrate', 'fps', 'audio_bitrate', 'sample_rate',
            'preset_speed', 'profile_level', 'pixel_format', 'tune', 'threads',
            'keyint', 'tag_hvc1', 'vf_lanczos', 'extra_args'
        )
        for key in extra_keys:
            val = kwargs.get(key)
            if val is None:
                continue
            if isinstance(val, bool):
                val = "1" if val else "0"
            else:
                val = str(val)
            ET.SubElement(preset_elem, key).text = val

        tree.write(self.presets_file, encoding='utf-8', xml_declaration=True)

    def removePreset(self, name):
        if not os.path.exists(self.presets_file):
            return
        tree = ET.parse(self.presets_file)
        root = tree.getroot()
        for preset in list(root):
            if preset.get('name') == name:
                root.remove(preset)
        tree.write(self.presets_file, encoding='utf-8', xml_declaration=True)

    def _elem_text(self, elem, default=""):
        if elem is None or elem.text is None:
            return default
        return elem.text

    def loadPreset(self, name):
        result = {}
        if not os.path.exists(self.presets_file):
            return result
        tree = ET.parse(self.presets_file)
        root = tree.getroot()
        for preset in root:
            if preset.get('name') == name:
                result['codec'] = self._elem_text(preset.find('codec'), '')
                result['resolution'] = self._elem_text(preset.find('resolution'), '')
                result['container'] = self._elem_text(preset.find('container'), '')
                result['description'] = self._elem_text(preset.find('description'), '')
                result['audio_codec'] = self._elem_text(preset.find('audio_codec'), '')
                result['crf'] = self._elem_text(preset.find('crf'), '0')
                result['bitrate'] = self._elem_text(preset.find('bitrate'), '0')
                result['fps'] = self._elem_text(preset.find('fps'), '0')
                result['audio_bitrate'] = self._elem_text(preset.find('audio_bitrate'), '0')
                result['sample_rate'] = self._elem_text(preset.find('sample_rate'), '0')
                result['preset_speed'] = self._elem_text(preset.find('preset_speed'), 'medium')
                result['profile_level'] = self._elem_text(preset.find('profile_level'), '')
                result['pixel_format'] = self._elem_text(preset.find('pixel_format'), '')
                result['tune'] = self._elem_text(preset.find('tune'), '')
                result['threads'] = self._elem_text(preset.find('threads'), '0')
                result['keyint'] = self._elem_text(preset.find('keyint'), '0')
                result['tag_hvc1'] = self._elem_text(preset.find('tag_hvc1'), '0')
                result['vf_lanczos'] = self._elem_text(preset.find('vf_lanczos'), '0')
                result['extra_args'] = self._elem_text(preset.find('extra_args'), '')
                break
        return result

    def presetNames(self):
        names = []
        if not os.path.exists(self.presets_file):
            return names
        tree = ET.parse(self.presets_file)
        root = tree.getroot()
        for preset in root:
            names.append(preset.get('name'))
        return names

    # ===== Новая логика для редактора пресетов =====

    def loadAllPresets(self):
        """Возвращает список словарей с данными по всем пресетам (включая все доп. поля)."""
        presets = []
        if not os.path.exists(self.presets_file):
            return presets
        defaults = {"description": "", "profile_level": "", "pixel_format": "", "tune": "",
                    "crf": "0", "bitrate": "0", "fps": "0", "audio_bitrate": "0", "sample_rate": "0",
                    "threads": "0", "keyint": "0", "tag_hvc1": "0", "vf_lanczos": "0",
                    "preset_speed": "medium", "audio_codec": "", "extra_args": ""}
        tree = ET.parse(self.presets_file)
        root = tree.getroot()
        for preset in root:
            data = {"name": preset.get("name", ""), "codec": "", "resolution": "", "container": ""}
            for key in ("codec", "resolution", "container", "description", "audio_codec",
                        "crf", "bitrate", "fps", "audio_bitrate", "sample_rate", "preset_speed",
                        "profile_level", "pixel_format", "tune", "threads", "keyint", "tag_hvc1", "vf_lanczos", "extra_args"):
                data[key] = self._elem_text(preset.find(key), defaults.get(key, ""))
            presets.append(data)
        return presets

    def exportPresetToFile(self, name, file_path):
        """Экспортирует один пресет в указанный XML-файл (включая все доп. поля)."""
        preset = self.loadPreset(name)
        if not preset:
            return False

        root = ET.Element("preset")
        root.set("name", name)
        for key in ("codec", "resolution", "container", "description", "audio_codec",
                    "crf", "bitrate", "fps", "audio_bitrate", "sample_rate", "preset_speed",
                    "profile_level", "pixel_format", "tune", "threads", "keyint", "tag_hvc1", "vf_lanczos", "extra_args"):
            val = preset.get(key, "")
            if isinstance(val, bool):
                val = "1" if val else "0"
            else:
                val = str(val) if val is not None else ""
            ET.SubElement(root, key).text = val

        tree = ET.ElementTree(root)
        tree.write(file_path, encoding="utf-8", xml_declaration=True)
        return True

    def importPresetFromFile(self, file_path):
        """Импортирует пресет из отдельного XML-файла (включая все доп. поля)."""
        if not os.path.exists(file_path):
            return False

        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            if root.tag != "preset":
                return False

            name = root.get("name", "imported_preset")
            codec = self._elem_text(root.find("codec"), "default")
            resolution = self._elem_text(root.find("resolution"), "default")
            container = self._elem_text(root.find("container"), "default")
            description = self._elem_text(root.find("description"), "")

            extra = {}
            for key in ("audio_codec", "crf", "bitrate", "fps", "audio_bitrate", "sample_rate",
                        "preset_speed", "profile_level", "pixel_format", "tune", "threads", "keyint", "tag_hvc1", "vf_lanczos", "extra_args"):
                extra[key] = self._elem_text(root.find(key), "")

            self.savePreset(name, codec, resolution, container, description, **extra)
            return True
        except ET.ParseError:
            return False
        except Exception:
            return False

    def mergePresetsFromFile(self, file_path):
        """Импортирует пресеты из файла, не перезаписывая существующие. При совпадении имени — заполняет только пустые поля."""
        if not os.path.exists(file_path):
            return False
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            if root.tag != "presets":
                return False
            existing = {p.get("name", ""): p for p in self.loadAllPresets()}
            for preset in root:
                name = preset.get("name", "")
                if not name:
                    continue
                incoming = {
                    "name": name,
                    "codec": self._elem_text(preset.find("codec"), ""),
                    "resolution": self._elem_text(preset.find("resolution"), ""),
                    "container": self._elem_text(preset.find("container"), ""),
                    "description": self._elem_text(preset.find("description"), ""),
                    "audio_codec": self._elem_text(preset.find("audio_codec"), ""),
                    "crf": self._elem_text(preset.find("crf"), "0"),
                    "bitrate": self._elem_text(preset.find("bitrate"), "0"),
                    "fps": self._elem_text(preset.find("fps"), "0"),
                    "audio_bitrate": self._elem_text(preset.find("audio_bitrate"), "0"),
                    "sample_rate": self._elem_text(preset.find("sample_rate"), "0"),
                    "preset_speed": self._elem_text(preset.find("preset_speed"), "medium"),
                    "profile_level": self._elem_text(preset.find("profile_level"), ""),
                    "pixel_format": self._elem_text(preset.find("pixel_format"), ""),
                    "tune": self._elem_text(preset.find("tune"), ""),
                    "threads": self._elem_text(preset.find("threads"), "0"),
                    "keyint": self._elem_text(preset.find("keyint"), "0"),
                    "tag_hvc1": self._elem_text(preset.find("tag_hvc1"), "0"),
                    "vf_lanczos": self._elem_text(preset.find("vf_lanczos"), "0"),
                    "extra_args": self._elem_text(preset.find("extra_args"), ""),
                }
                if name not in existing:
                    self.savePreset(
                        name,
                        incoming["codec"],
                        incoming["resolution"],
                        incoming["container"],
                        incoming["description"],
                        **{k: incoming[k] for k in incoming if k not in ("name", "codec", "resolution", "container", "description")}
                    )
                else:
                    current = existing[name]
                    merged = {}
                    for k, v in incoming.items():
                        if k == "name":
                            continue
                        cur = current.get(k, "")
                        if str(cur).strip() in ("", "0") and str(v).strip() not in ("", "0"):
                            merged[k] = v
                    if merged:
                        self.savePreset(
                            name,
                            current.get("codec", ""),
                            current.get("resolution", ""),
                            current.get("container", ""),
                            current.get("description", ""),
                            **merged
                        )
            return True
        except Exception:
            return False
