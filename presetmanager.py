import xml.etree.ElementTree as ET
import os

class PresetManager:
    def __init__(self):
        # Путь к presets.xml рядом с exe или скриптом
        self.presets_file = os.path.join(os.path.dirname(__file__), 'presets.xml')

    def savePreset(self, name, codec, resolution, container, description=""):
        if os.path.exists(self.presets_file):
            tree = ET.parse(self.presets_file)
            root = tree.getroot()
        else:
            root = ET.Element('presets')
            tree = ET.ElementTree(root)

        # Удаляем старый пресет если есть
        for preset in list(root):
            if preset.get('name') == name:
                root.remove(preset)

        # Добавляем новый
        preset_elem = ET.SubElement(root, 'preset')
        preset_elem.set('name', name)
        ET.SubElement(preset_elem, 'codec').text = codec
        ET.SubElement(preset_elem, 'resolution').text = resolution
        ET.SubElement(preset_elem, 'container').text = container
        desc_elem = ET.SubElement(preset_elem, 'description')
        desc_elem.text = description if description else ""

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

    def loadPreset(self, name):
        result = {}
        if not os.path.exists(self.presets_file):
            return result
        tree = ET.parse(self.presets_file)
        root = tree.getroot()
        for preset in root:
            if preset.get('name') == name:
                result['codec'] = preset.find('codec').text
                result['resolution'] = preset.find('resolution').text
                result['container'] = preset.find('container').text
                desc_elem = preset.find('description')
                result['description'] = desc_elem.text if desc_elem is not None and desc_elem.text else ""
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
        """Возвращает список словарей с данными по всем пресетам."""
        presets = []
        if not os.path.exists(self.presets_file):
            return presets
        tree = ET.parse(self.presets_file)
        root = tree.getroot()
        for preset in root:
            data = {
                "name": preset.get("name", ""),
                "codec": "",
                "resolution": "",
                "container": "",
                "description": "",
            }
            codec_elem = preset.find("codec")
            res_elem = preset.find("resolution")
            cont_elem = preset.find("container")
            desc_elem = preset.find("description")
            if codec_elem is not None and codec_elem.text is not None:
                data["codec"] = codec_elem.text
            if res_elem is not None and res_elem.text is not None:
                data["resolution"] = res_elem.text
            if cont_elem is not None and cont_elem.text is not None:
                data["container"] = cont_elem.text
            if desc_elem is not None and desc_elem.text is not None:
                data["description"] = desc_elem.text
            presets.append(data)
        return presets

    def exportPresetToFile(self, name, file_path):
        """Экспортирует один пресет в указанный XML-файл."""
        preset = self.loadPreset(name)
        if not preset:
            return False

        root = ET.Element("preset")
        root.set("name", name)
        ET.SubElement(root, "codec").text = preset.get("codec", "")
        ET.SubElement(root, "resolution").text = preset.get("resolution", "")
        ET.SubElement(root, "container").text = preset.get("container", "")
        desc_elem = ET.SubElement(root, "description")
        desc_elem.text = preset.get("description", "") or ""

        tree = ET.ElementTree(root)
        tree.write(file_path, encoding="utf-8", xml_declaration=True)
        return True

    def importPresetFromFile(self, file_path):
        """Импортирует пресет из отдельного XML-файла."""
        if not os.path.exists(file_path):
            return False

        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            if root.tag != "preset":
                return False

            name = root.get("name", "imported_preset")
            codec_elem = root.find("codec")
            res_elem = root.find("resolution")
            cont_elem = root.find("container")
            desc_elem = root.find("description")

            codec = codec_elem.text if codec_elem is not None else "default"
            resolution = res_elem.text if res_elem is not None else "default"
            container = cont_elem.text if cont_elem is not None else "default"
            description = desc_elem.text if desc_elem is not None and desc_elem.text else ""

            self.savePreset(name, codec, resolution, container, description)
            return True
        except ET.ParseError:
            return False
        except Exception:
            return False
