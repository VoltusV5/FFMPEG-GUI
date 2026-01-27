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
