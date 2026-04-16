from __future__ import annotations
# Basic Modules
import sys, os, shutil, re
import numpy as np
from io import BytesIO
from copy import deepcopy
from tempfile import NamedTemporaryFile
import xml.etree.ElementTree as ET
from pathlib import Path
from collections import defaultdict
from enum import Enum, auto
from PIL import Image, ImageDraw, UnidentifiedImageError
from datetime import datetime
import traceback
# GUI
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QCheckBox, QDialog,
QLabel, QHBoxLayout, QFileDialog, QPushButton, QMessageBox, QSplitter, QProgressDialog, QInputDialog, QLineEdit, QComboBox, QMenu)
from PySide6.QtGui import QPixmap, QImage, QIcon, QDesktopServices, QAction
from PySide6.QtCore import Qt, QObject, QThread, QUrl, Signal, QPoint
# Soulstruct
from soulstruct.containers import tpf, Binder, BinderEntry, BinderVersion, BinderVersion4Info
from soulstruct.dcx import core, oodle, DCXType
# Custom
from GameInfo import Maps, Types

BLANK_PATH = Path('.')
ROOTS = {
        "Sekiro": Path(r"N:\NTC\data\Menu\ScaleForm\SBLayout\01_Common"),

        "Elden Ring": Path(r"N:\GR\data\Menu\ScaleForm\SBLayout\01_Common"),

        "Nightreign": Path(r"W:\CL\data\Target\INTERROOT_win64\menu\ScaleForm\Tif"),
    }

class NaturalListItem(QListWidgetItem):
    def __init__(self, text):
        super().__init__(text)
        self._key = Functions.naturalSortKey(text)

    def __lt__(self, other):
        return self._key < other._key

class ExportMode(Enum):
    ATLAS = auto()
    SUBTEXTURE = auto()

class GameType(Enum):
    OLD = auto()
    MODERN = auto()

class Modified(Enum):
    FALSE = auto()
    ADDED = auto()
    REPLACED = auto()

class Game():
    OLD_GAMES = {"Dark Souls 1", "Dark Souls 2", "Dark Souls 3"}

    def __init__(self, name: str):
        self.name = name
        self.type = self.classify(name)

    def classify(self, name: str) -> GameType:
        if name in self.OLD_GAMES:
            return GameType.OLD
        else:
            return GameType.MODERN

    def __repr__(self):
        return f"Game({self.name}, {self.type.name})"

class ResFormat(Enum):
    NIGHTREIGN = ("Nightreign", {"H": "High", "L": "Low"})
    ELDEN_RING = ("Elden Ring", {"H": "Hi", "L": "Low"})
    SEKIRO = ("Sekiro", {"H": "Hi", "L": "Low"})

    def __init__(self, game_name: str, mapping: dict[str, str]):
        self.game_name = game_name
        self.mapping = mapping

    def get(self, res: str) -> str:
        return self.mapping.get(res, res)

    @classmethod
    def from_name(cls, name: str):
        for g in cls:
            if g.game_name == name:
                return g
        raise ValueError(f"Unknown game: {name}")

class Functions():
    @staticmethod
    def processLayout(queue, output_dir: Path, game: Game, base_name, format_mode):
        for _, additions in queue.items():
            data = additions['data']
            to_add = additions['additions']
            output_name = additions['output']

            binder = Binder(
                version=BinderVersion.V4,
                dcx_type=DCXType.DCX_KRAK,
                v4_info=BinderVersion4Info.eldenring_default())
            
            _format = ResFormat.from_name(game.name)
            root = ROOTS.get(game.name, "") / base_name / _format.get(format_mode)

            for atlas in data:
                atlas_path = Functions.replaceTerms(atlas.get("imagePath"), {'.png': '', '.tif': ''})
                atlas_subtextures = [sub for sub in to_add if sub.get("parent") in atlas_path]

                Functions.addSubtexturesToAtlasLayout(atlas, atlas_subtextures)

            for atlas in data:
                xml_bytes = ET.tostring(atlas, encoding='utf-8', method='xml', )
                layout_path = Functions.replaceTerms(atlas.get("imagePath"), {'.png': '.layout', '.tif': '.layout'})
                entry = BinderEntry(
                    data=xml_bytes,
                    entry_id=binder.get_first_new_entry_id_in_range(0, 1000000),
                    path=str(root / layout_path),
                    flags=0x2)
                
                binder.add_entry(entry=entry)

            binder.write(output_dir / output_name)

    @staticmethod
    def getFreeSpace(atlas_size, used_rects, w, h, step=4, padding=2):
        atlas_w, atlas_h = atlas_size

        for y in range(0, atlas_h - h, step):
            for x in range(0, atlas_w - w, step):

                new_rect = (x - padding, y - padding, x + w + padding, y + h + padding)

                overlap = False
                for r in used_rects:
                    if not (
                        new_rect[2] <= r[0] or  # left
                        new_rect[0] >= r[2] or  # right
                        new_rect[3] <= r[1] or  # above
                        new_rect[1] >= r[3]     # below
                    ):
                        overlap = True
                        break

                if not overlap:
                    return x, y

        return None
    
    @staticmethod
    def addSubtexturesToAtlasLayout(atlas: ET.Element, subtextures: list[dict]):
        for sub in subtextures:
            name = sub.get('name')
            if not name.endswith('.png'):
                name = f"{name}.png"

            if any(child.get('name') == name for child in atlas):
                print("Subtexture entry already exists in layout file. Skipping.")
                continue

            item = ET.SubElement(atlas, "SubTexture", {
                "name": name,
                "x": sub.get('x'),
                "y": sub.get('y'),
                "width": sub.get('width'),
                "height": sub.get('height'),
                "half": sub.get('half')})
            
            print(f"Adding Subtexture to {sub.get('parent')}:\n{ET.tostring(item, encoding='unicode')}")
            
            if len(atlas) == 1:
                atlas.text = '\r\n\t'
            else:
                atlas[-2].tail = '\r\n\t'

            item.tail = '\r\n'
        
    @staticmethod
    def cleanByAlpha(img: Image.Image, threshold: int = 5) -> Image.Image:
        """Zero RGB values where alpha <= threshold."""
        arr = np.array(img)
        r, g, b, a = arr[..., 0], arr[..., 1], arr[..., 2], arr[..., 3]
        mask = a <= threshold

        r[mask] = 0
        g[mask] = 0
        b[mask] = 0

        arr[..., 0] = r
        arr[..., 1] = g
        arr[..., 2] = b

        return Image.fromarray(arr, "RGBA")
    
    @staticmethod
    def naturalSortKey(text):
        return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', text)]
    
    @staticmethod
    def replaceTerms(text, terms: dict):
        if text:
            for term, replacement in terms.items():
                text = text.replace(term, replacement)
        return text
    
    @staticmethod
    def getLayoutData(dcx_path):
        with open(dcx_path, "rb") as f:
            decompressed_bytes, _ = core.decompress(f)
            start_index = decompressed_bytes.find(b"<TextureAtlas")
            xml_bytes = decompressed_bytes[start_index:]
            xml_text = xml_bytes.decode("utf-8", errors="ignore").replace("\x00", "")
            return f"<Root>{xml_text}</Root>"

    @staticmethod
    def parseGameType(path):
        game_type = None
        if "DARK SOULS REMASTERED" in path:
            game_type = 'Dark Souls 1'
        elif "Dark Souls II Scholar of the First Sin" in path:
            game_type = 'Dark Souls 2'
        elif "DARK SOULS III" in path:
            game_type = 'Dark Souls 3'
        elif "Sekiro" in path:
            game_type = 'Sekiro'
        elif "ELDEN RING NIGHTREIGN" in path:
            game_type = 'Nightreign'
        elif "ELDEN RING" in path:
            game_type = 'Elden Ring'
        return game_type

    @staticmethod
    def gameTypeDialog():
        options = ["Dark Souls 1", "Dark Souls 2", "Dark Souls 3", "Sekiro", "Elden Ring", "Nightreign",]
        choice, ok = QInputDialog.getItem(None, "Select Game Type", "Choose one of the following:", options, 0, False)

        if choice and ok:
            return choice
        return None

    @staticmethod
    def createDebugGrid(image, subtextures):
        """Outputs a png with grid lines for debugging"""
        if len(subtextures) == 0:
            return image
        
        debug = image.copy()
        draw = ImageDraw.Draw(debug)

        for icn in subtextures.values():
            width = icn['width']
            height = icn['height']
            x = icn['x']
            y = icn['y']
            draw.rectangle([x, y, x + width, y + height], outline="red", width=1)

        return debug

class LoadWorker(QObject):
    progress = Signal(int, str)   # percent, message
    finished = Signal(dict, dict, dict, dict)  # atlases, subtextures, loaded dcx files, parsed xml data

    def __init__(self, file_mappings, game: Game):
        super().__init__()
        self.file_mappings = file_mappings
        self.game = game
        self.LOADED_DCX_FILES = {}
        self.LAYOUT_FILES = {}

    def run(self):
        if self.game.type == GameType.OLD:
            self.processOld()
        else: # sblyt is used
            self.processModern()

    def generateTextDict(self, dcx_path, percent):
        textures_dict: dict = {}
        self.progress.emit(percent, f"Unpacking {dcx_path.stem}...")

        paths = []
        if dcx_path.is_dir():
            paths = [Path(dcx_path) / f for f in os.listdir(dcx_path) if f.endswith('tpf.dcx') or f.endswith('.tpf')]
        else:
            paths = [Path(dcx_path)]

        for path in paths:
            tpfdcx = tpf.TPF(path)
            self.LOADED_DCX_FILES[path.name] = tpfdcx
            for texture in tpfdcx.textures:
                textures_dict[texture.stem] = texture

        self.progress.emit(percent, f"Loaded {dcx_path.stem}")
        return textures_dict

    def processModern(self):
        try:
            atlases = {}
            subtextures = {}
            total_files = len(self.file_mappings)

            self.progress.emit(0, f'Loading {total_files} files...')
            for f_idx, file in enumerate(self.file_mappings, 1):
                percent = int(f_idx / total_files * 100 - 1)
                if isinstance(file, dict):
                    layout_path = file['layout']
                    textures_dict: dict = self.generateTextDict(file['file'], percent)

                    layout_xml = Functions.getLayoutData(layout_path)
                    root = ET.fromstring(layout_xml, parser=ET.XMLParser(encoding="utf-8"))
                    self.progress.emit(percent, "Parsing layout XML...")

                    atlas_nodes = root.findall("TextureAtlas")
                    self.LAYOUT_FILES[file['file'].name] = atlas_nodes
                    total_atlases = len(atlas_nodes)

                    if total_atlases == 0:
                        self.progress.emit(100, "No atlases found")
                        self.finished.emit({}, {}, {}, {})
                        return

                    for texture_atlas in atlas_nodes:
                        filepath = texture_atlas.get("imagePath")
                        filename = Path(filepath).stem

                        if filename not in textures_dict:
                            self.progress.emit(int(f_idx / total_files * 100), f"{filename} not found, skipping.")
                            continue

                        atlases[filename] = {"texture": textures_dict[filename], "parent": file['file']}  # store raw texture
                        subtextures[filename] = {}

                        for sub in texture_atlas.findall("SubTexture"):
                            subtextures[filename][sub.get("name").replace('.png', '')] = {
                                "x": int(sub.get("x")),
                                "y": int(sub.get("y")),
                                "width": int(sub.get("width")),
                                "height": int(sub.get("height")),
                                "blank": False}

                elif isinstance(file, Path):
                    textures_dict: dict = self.generateTextDict(file, percent)
                    # add any textures that were not included in the layout
                    for name, texture in textures_dict.items():
                        if name not in atlases:
                            atlases[name] = {"texture": texture, "parent": file}
                            subtextures[name] = {}  # no layout info since single textures go to atlases

            self.finished.emit(atlases, subtextures, self.LOADED_DCX_FILES, self.LAYOUT_FILES)
            self.progress.emit(100, 'Successfully loaded all files!')

        except Exception as e:
            print(e)
            self.progress.emit(0, f"Error: {e}")
            self.finished.emit({}, {}, {}, {})

    def processOld(self):  
        try:
            atlases = {}
            subtextures = {}
            total_files = len(self.file_mappings)

            for f_idx, file in enumerate(self.file_mappings, 1):
                percent = int(f_idx / total_files * 100 - 1)
                textures_dict: dict = self.generateTextDict(file, percent)

                for name, texture in textures_dict.items():
                    atlases[name] = {"texture": texture, "parent": file}
                    subtextures[name] = {}
                    dds = texture.get_dds()
                    image = Image.open(BytesIO(dds.to_bytes())).convert("RGBA")

                    texmap = Maps.TextureDimensions[self.game.name]
                    dimensions = texmap.get(name, None)
                    if dimensions:
                        tile_width, tile_height = dimensions['width'], dimensions['height']

                        atlas_width, atlas_height = dds.header.width, dds.header.height
                        tiles_per_row = atlas_width // tile_width
                        tiles_per_column = atlas_height // tile_height

                        total_tiles = tiles_per_row * tiles_per_column

                        for idx in range(total_tiles):
                            row = idx // tiles_per_row
                            col = idx % tiles_per_row
                            x = col * tile_width
                            y = row * tile_height

                            tile = image.crop((x, y, x + tile_width, y + tile_height))
                            alpha = np.array(tile.getchannel("A"))
                            opacity_ratio = np.count_nonzero(alpha) / alpha.size
                            isBlank: bool = opacity_ratio < 0.01

                            subtextures[name][str(idx)] = {
                                "x": x,
                                "y": y,
                                "width": tile_width,
                                "height": tile_height,
                                "blank": isBlank}

                        self.progress.emit(percent, f"Processed {name}")

            self.finished.emit(atlases, subtextures, self.LOADED_DCX_FILES, {})

        except Exception as e:
            print(e)
            self.progress.emit(0, f"Error: {e}")
            self.finished.emit({}, {}, {}, {})

class ExtractWorker(QObject):
    progress = Signal(int, str) # percent, message
    finished = Signal(bool) # success

    def __init__(self, atlases, subtextures, output_dir, loader, tasks=None, mode=ExportMode.SUBTEXTURE, filetype='png'):
        super().__init__()
        self.atlases = atlases
        self.subtextures = subtextures
        self.output_dir = output_dir
        self.pilLoader = loader
        self.tasks = tasks if tasks is not None else []
        self.mode = mode
        self.filetype = filetype
        self._interrupted = False

    def interrupt(self):
        self._interrupted = True

    def exportImg(self, image, filename, out_path, progress, message):
        out_path = Path(out_path)
        if not out_path.exists():
            out_path.mkdir(parents=True, exist_ok=True)
        if not filename.endswith('.png'):
            filename = f"{filename}.png"
        image.save(out_path / filename)
        self.progress.emit(progress, message)

    def run(self):
        if not self.tasks: # dump mode
            if self.mode == ExportMode.ATLAS:
                if not self.atlases:
                    self.finished.emit(False)
                    return

                for atlas_name in self.atlases:
                    self.tasks.append((atlas_name, None))

            elif self.mode == ExportMode.SUBTEXTURE:
                if not self.subtextures:
                    self.finished.emit(False)
                    return

                for atlas_name, atlas_img in self.atlases.items():
                        for st in self.subtextures.get(atlas_name, []):
                            self.tasks.append((atlas_name, st))

        total = len(self.tasks)
        for i, (atlas_name, st) in enumerate(self.tasks, 1):
            if self._interrupted:
                break
            
            if self.filetype == 'dds':
                texture: tpf.TPFTexture = self.atlases[atlas_name]['texture']
                texture.write_dds(Path(self.output_dir) / ".Atlases" / f"{atlas_name}.dds")
                self.progress.emit(100, f"Exported atlas: {atlas_name}")

            else:
                atlas_img = self.pilLoader(atlas_name=atlas_name)
                percent = int(i / total * 100 - 1)

                if self.mode == ExportMode.ATLAS:
                    out_path = self.output_dir / '.Atlases'
                    filename = atlas_name
                    message = f"Exported atlas: {atlas_name}"

                elif self.mode == ExportMode.SUBTEXTURE:
                    out_path = self.output_dir / atlas_name
                    filename = st
                    message = f"Exported {st} from {atlas_name}"
                    st = self.subtextures[atlas_name][st]
                    atlas_img = atlas_img.crop((st["x"], st["y"], st["x"] + st["width"], st["y"] + st["height"])) # crop if in subtexture mode

                self.exportImg(image=atlas_img, filename=filename, out_path=out_path, progress=percent, message=message)

        self.finished.emit(True)

class SearchWindow(QWidget):
    results = Signal(str, bool) # text, atlas search mode

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Search")
        layout = QVBoxLayout()

        layout.addWidget(QLabel("Search text:"))
        self.search_input = QLineEdit()

        self.atlas_search = QCheckBox("Search Atlases")

        flags_layout = QVBoxLayout()
        flags_layout.addWidget(self.atlas_search)

        self.search_button = QPushButton("Search")
        layout.addWidget(self.search_input)
        layout.addLayout(flags_layout)
        layout.addWidget(self.search_button)

        self.setLayout(layout)
        self.search_button.clicked.connect(self.emit_search)

    def emit_search(self):
        text = self.search_input.text()
        self.results.emit(text, self.atlas_search.isChecked())

class TextureNamePrompt(QDialog):
    def __init__(self, halfprompt=True):
        super().__init__()
        self.halfprompt = halfprompt
        self.setWindowTitle("Prompt")

        layout = QVBoxLayout()

        layout.addWidget(QLabel("Prefix:"))
        self.prefix_input = QComboBox()
        self.prefix_input.addItems(Types.SubtexturePrefix)
        self.prefix_input.setEditable(True)
        layout.addWidget(self.prefix_input)

        layout.addWidget(QLabel("Icon ID:"))
        self.id_input = QLineEdit()
        layout.addWidget(self.id_input)

        if self.halfprompt:
            self.half_checkbox = QCheckBox("Half")
            layout.addWidget(self.half_checkbox)

        self.submit_button = QPushButton("Submit")
        layout.addWidget(self.submit_button)

        self.setLayout(layout)

        self.submit_button.clicked.connect(self.accept)

    def get_result(self):
        if self.halfprompt:
            half = self.half_checkbox.isChecked()
        else:
            half = False

        id = self.id_input.text()
        if not id.isdigit() or not 0 <= int(id) < 65536:
            MainWindow.showError(None, "Inputted ID is not an asserted UInt16.\nThis may silently throw errors in Smithbox or elsewhere.\nRename this icon if that wasn't your intention.", "Warning", QMessageBox.Warning)
        return f"{self.prefix_input.currentText()}_{id}", half

class ReplaceWorker(QObject):
    finished = Signal(bool, str)  # success, message

    def __init__(self, replacements, additions, subtextures, loaded_files, layouts, getPilImage, project_dir, game, resolutions):
        super().__init__()
        self.replacements = replacements
        self.additions = additions
        self.subtextures = subtextures
        self.getPilImage = getPilImage
        self.output_dir = project_dir / "Output" / ".DCX Files" / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.LOADED_DCX_FILES = loaded_files
        self.LAYOUT_FILES = layouts
        self.game = game
        self.RESOLUTIONS = resolutions

    def buildOperations(self):
        print("Building operations map...")
        dcx_ops = {}

        for dcx_path, atlases in self.replacements.items():
            base_name = Path(dcx_path).name
            dcx_ops.setdefault(base_name, {})

            for atlas_name, changes in atlases.items():
                dcx_ops[base_name].setdefault(atlas_name, {"replacements": {}, "additions": []})
                dcx_ops[base_name][atlas_name]["replacements"].update(changes)

        for dcx_path, add_data in self.additions.items():
            base_name = Path(dcx_path).name

            if dcx_path in self.LAYOUT_FILES:
                print(f"Processing layout for: {base_name}")
                lyt_name = Functions.replaceTerms(base_name.split('.')[0], {"_h": "", "_l": ""}) if self.game.name == 'Nightreign' else ""
                Functions.processLayout({dcx_path: add_data}, self.output_dir, self.game, lyt_name, format_mode=self.RESOLUTIONS.get(lyt_name, "H"))

            additions_by_atlas = {}
            for sub in add_data["additions"]:
                if "parent" not in sub:
                    continue
                atlas_name = sub["parent"]
                additions_by_atlas.setdefault(atlas_name, []).append(sub)

            for atlas_name, subs in additions_by_atlas.items():
                dcx_ops.setdefault(base_name, {})
                dcx_ops[base_name].setdefault(atlas_name, {"replacements": {}, "additions": []})
                dcx_ops[base_name][atlas_name]["additions"].extend(subs)

        print("\nFinished building operations.")
        print("Summary of DCX operations:")
        for dcx_name, atlases in dcx_ops.items():
            print(f"File: {dcx_name}")
            for atlas_name, ops in atlases.items():
                rep_keys = list(ops['replacements'].keys())
                add_names = [sub['name'] for sub in ops['additions']]
                print(f"  Atlas: {atlas_name} | Replacements: {rep_keys if rep_keys != [None] else ['*Self*']} | Additions: {add_names}")

        return dcx_ops

    def run(self):
        try:
            for base_name, atlases in self.buildOperations().items():
                base = deepcopy(self.LOADED_DCX_FILES[base_name])
                atlas_cache = {}

                for atlas_name, ops in atlases.items():
                    if atlas_name not in atlas_cache:
                        atlas_cache[atlas_name] = self.getPilImage(atlas_name).copy()
                    atlas_img = atlas_cache[atlas_name]

                    for add in ops["additions"]:
                        x, y = int(add["x"]), int(add["y"])
                        atlas_img.paste(add["img"], (x, y))

                    for sub_name, new_img in ops["replacements"].items():
                        if sub_name:  # subtexture replacement
                            st = self.subtextures.get(atlas_name, {}).get(sub_name)
                            if not st:
                                raise Exception(f"Could not resolve subtexture '{sub_name}' in atlas '{atlas_name}'")
                            atlas_img.paste(new_img, (st["x"], st["y"]))
                        else:  # full atlas replacement
                            atlas_img = new_img.copy()
                            atlas_cache[atlas_name] = atlas_img

                for atlas_name, atlas_img in atlas_cache.items():
                    with NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                        temp_path = tmp.name
                        atlas_img.save(temp_path)
                    try:
                        texture = tpf.TPF.find_texture_stem(base, atlas_name)
                        texture.replace_dds(temp_path)
                    finally:
                        if os.path.exists(temp_path):
                            os.remove(temp_path)

                writer = base.to_writer()
                data = core.compress(bytes(writer), DCXType.DCX_KRAK)
                with open(self.output_dir / base_name, "wb") as f:
                    f.write(data)

            self.finished.emit(True, "All changes applied successfully!")

        except Exception:
            self.finished.emit(False, traceback.format_exc())

class MainWindow(QMainWindow):
    def __init__(self, project_dir):
        super().__init__()
        self.project_dir = project_dir
        self.alphaThreshold = 0

        self.setWindowTitle("DSIE")
        self.setGeometry(100, 100, 1100, 700)
        self.createMenu()

        self.current_crop = None
        self.current_atlas = None
        self.thumbnail_cache = {}
        self.pending_replacements = {}
        self.pending_additions = {}
        self.RESOLUTIONS = {}

        container = QWidget()
        layout = QHBoxLayout(container)
        splitter = QSplitter(Qt.Horizontal)

        self.atlas_list = QListWidget()
        self.atlas_list.currentItemChanged.connect(self.showAtlas)
        #self.atlas_list.itemClicked.connect(self.showAtlas)
        splitter.addWidget(self.atlas_list)

        self.subtexture_list = QListWidget()
        self.subtexture_list.currentItemChanged.connect(self.showSubtexture)
        #self.subtexture_list.itemClicked.connect(self.showSubtexture)
        self.subtexture_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.subtexture_list.customContextMenuRequested.connect(self.openSubtextureMenu)
        splitter.addWidget(self.subtexture_list)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        self.preview_label = QLabel("Texture Preview")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("border: 1px solid gray; background: #222; color: white;")
        self.preview_label.setFixedSize(600, 400)  # smaller preview box
        right_layout.addWidget(self.preview_label, alignment=Qt.AlignCenter)

        self.info_label = QLabel("Texture Info")
        self.info_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.info_label.setStyleSheet("background: #333; color: white; padding: 6px; border-radius: 4px;")
        self.info_label.setFixedHeight(150)  # fixed space for info text
        right_layout.addWidget(self.info_label)

        self.save_button = QPushButton("Export Selected Texture")
        self.save_button.clicked.connect(self.saveSelection)
        right_layout.addWidget(self.save_button)

        self.replace_button = QPushButton("Replace Selected Texture")
        self.replace_button.clicked.connect(self.registerReplacement)
        right_layout.addWidget(self.replace_button)

        splitter.addWidget(right_panel)

        layout.addWidget(splitter)
        self.setCentralWidget(container)

    def createMenu(self):
        """Handles the creation of the menu bar and its features."""
        menu = self.menuBar()
        def createAction(name, func):
            action = QAction(name, self)
            action.triggered.connect(func)
            return action

        self.file_menu = menu.addMenu("File")
        self.file_menu.addAction(createAction("Open File", lambda: self.openDcxDialog(dirmode=False)))
        self.file_menu.addAction(createAction("Open Directory", lambda: self.openDcxDialog(dirmode=True)))
        self.file_menu.addAction(createAction("Clear", self.clear))
        self.file_menu.addAction(createAction("Apply Changes", self.applyChanges))
        self.file_menu.addSeparator()
        self.file_menu.addAction(createAction("Dump All Atlases", lambda: self.dumpTextures(mode=ExportMode.ATLAS)))
        self.file_menu.addAction(createAction("Dump All Subtextures", lambda: self.dumpTextures(mode=ExportMode.SUBTEXTURE)))
        self.file_menu.addSeparator()
        self.file_menu.addAction(createAction("Exit", self.close))

        self.settings_menu = menu.addMenu("Settings")

        self.btn_useCustomNames = QAction("Custom Names", self)
        self.btn_useCustomNames.setCheckable(True)
        self.btn_useCustomNames.toggled.connect(self.toggleCustomNames)

        self.btn_calcImageSize = QAction("Calculate Image Size", self)
        self.btn_calcImageSize.setCheckable(True)

        self.btn_hideBlankIcons = QAction("Hide Blank Icons", self)
        self.btn_hideBlankIcons.setCheckable(True)
        self.btn_hideBlankIcons.setChecked(True)
        self.btn_hideBlankIcons.toggled.connect(lambda: self.showAtlas(self.atlas_list.currentItem()))

        self.btn_atlasGrid = QAction("Show Icon Borders", self)
        self.btn_atlasGrid.setCheckable(True)
        self.btn_atlasGrid.toggled.connect(lambda: self.showAtlas(self.atlas_list.currentItem()))

        self.btn_alphaThreshold = QAction(f"Alpha Threshold = {self.alphaThreshold}", self)
        self.btn_alphaThreshold.triggered.connect(self.promptAlphaThreshold)

        self.settings_menu.addAction(self.btn_useCustomNames)
        self.settings_menu.addAction(self.btn_hideBlankIcons)
        self.settings_menu.addAction(self.btn_calcImageSize)
        self.settings_menu.addAction(self.btn_atlasGrid)
        self.settings_menu.addSeparator()
        self.settings_menu.addAction(self.btn_alphaThreshold)
        
        self.searchButton = menu.addAction(createAction("Search", self.openSearchWindow))
        self.searchButton = menu.addAction(createAction("Add", self.addIcon))

        self.help_menu = menu.addMenu("Help")
        self.help_menu.addAction(createAction("Settings", lambda: QMessageBox.information(self, "Settings", "<b>Custom Names:</b><br> When enabled, this setting replaces" \
                                                                                                " most atlas and subtexture names with more user-friendly ones. " \
                                                                                                "The new atlas names were written manually by me, and are not " \
                                                                                                "perfect. However, they may help someone less familiar with fromsoft " \
                                                                                                "find what they are looking for. Most subtexture names were mapped " \
                                                                                                "with a script using data from Smithbox exports, and should"
                                                                                                " be accurate.<br><br>" \
                                                                                                "<b>Hide Blank Icons:</b><br>" \
                                                                                                "Only for older games with no layout system. DSIE crops the atlases" \
                                                                                                " in a grid layout. Because of this, some \'tiles\' may be blank. " \
                                                                                                "DSIE automatically recognises these blank spaces and ignores them " \
                                                                                                "when building the subtexture list. Disable this setting to show " \
                                                                                                "the aforementioned blank spaces, for example, if you wanted to " \
                                                                                                "place a new icon in that spot.<br><br>" \
                                                                                                "<b>Calculate Image Size:</b><br>" \
                                                                                                "When enabled, this setting will attempt to silently convert " \
                                                                                                "images to PNGs within memory in order to estimate their " \
                                                                                                "compressed size. This may be useful for someone doing batch " \
                                                                                                "exports, but it slows loading time substantially, so it's " \
                                                                                                "disabled by default.<br><br>" \
                                                                                                "<b>Show Icon Borders:</b><br>" \
                                                                                                "Draws a red bounding box around subtextures wherever possible. " \
                                                                                                "This will not be visible on texture dumps or replacements, " \
                                                                                                "but can be optionally selected for atlas exports.<br><br>" \
                                                                                                "<b>Alpha Threshold:</b><br>" \
                                                                                                "Any pixel with an alpha value less than or equal to this number " \
                                                                                                "will have their RGB values set to 0. Click to update the value.")))
        self.help_menu.addAction(createAction("Replacement", lambda: QMessageBox.information(self, "Replacement", 
                                                                                         "Pressing \"Replace\" will prompt you for an image file.<br>" \
                                                                                         "DSIE will then replace the currently selected texture, whether that be" \
                                                                                         " an atlas or a subtexture.<br><br>After replacing, go to" \
                                                                                         " File->Apply Changes to save. This may take a while.")))
        self.help_menu.addAction(createAction("Adding Icons", lambda: QMessageBox.information(self, "Adding Icons", 
                                                                                         "Pressing \"Add\" will prompt you for an image file.<br>" \
                                                                                         "DSIE will then append the image to the current selected atlas," \
                                                                                         " if possible.<br><br>Afterwards, go to" \
                                                                                         " File->Apply Changes to save. This may take a while.")))
        self.help_menu.addAction(createAction("About", lambda: QMessageBox.information(self, "About", 
                                                                                       "Made by <a href='https://linktr.ee/aerolitesr'>Aero</a> :><br><br>")))

    def openSubtextureMenu(self, position: QPoint):
        item = self.subtexture_list.itemAt(position)
        if item is None:
            return
        
        current = self.atlas_list.currentItem()
        atlas_name = current.data(Qt.UserRole)
        dcx_file = Path(current.data(Qt.UserRole+1)).name
        sub_name = item.data(Qt.UserRole)

        #print(dcx_file, atlas_name, sub_name)
        modify = self.isModified(dcx_file, atlas_name, sub_name)
        if modify == Modified.FALSE:
            return # return on vanilla items, no reason to edit them

        self.subtexture_list.setCurrentItem(item)

        menu = QMenu()

        delete_action = QAction("Delete", self)
        delete_action.triggered.connect(lambda: self.deleteSubtexture(item))

        rename_action = QAction("Rename", self)
        rename_action.triggered.connect(lambda: self.renameSubtexture(item))

        revert_action = QAction("Revert", self)
        revert_action.triggered.connect(lambda: self.revertSubtexture(item))

        if modify == Modified.ADDED:
            menu.addAction(delete_action)
            menu.addAction(rename_action)
        elif modify == Modified.REPLACED:
            menu.addAction(revert_action)

        menu.exec(self.subtexture_list.viewport().mapToGlobal(position))

    def deleteSubtexture(self, sub_item):
        """Delete a subtexture, update dicts."""
        atlas_item = self.atlas_list.currentItem()
        if not atlas_item or not sub_item:
            return
        
        atlas_name = atlas_item.data(Qt.UserRole)
        dcx_file = Path(atlas_item.data(Qt.UserRole+1)).name
        sub_name = sub_item.data(Qt.UserRole)

        if atlas_name in self.subtextures and sub_name in self.subtextures[atlas_name]:
            del self.subtextures[atlas_name][sub_name]

        for _, info in list(self.pending_additions.items()):
            additions = info.get("additions", [])
            info["additions"] = [a for a in additions if a.get("name") != sub_name]
            if len(info['additions']) == 0:
                del self.pending_additions[dcx_file]

        self.rebuildAtlas(atlas_name, dcx_file)

        items = [self.subtexture_list.item(i) for i in range(self.subtexture_list.count())]
        if all(self.isModified(dcx_file, atlas_name, item.data(Qt.UserRole)) == Modified.FALSE for item in items):
            atlas_item.setForeground(Qt.white)

        self.subtexture_list.takeItem(self.subtexture_list.row(sub_item))
        self.showAtlas(atlas_item)

    def renameSubtexture(self, sub_item):
        """Rename a subtexture and update all relevant dicts."""
        atlas_item = self.atlas_list.currentItem()
        if not atlas_item or not sub_item:
            return

        atlas_name = atlas_item.data(Qt.UserRole)
        old_name = sub_item.data(Qt.UserRole)

        dialog = TextureNamePrompt(halfprompt=False)
        if not dialog.exec():
            return
        new_name, _ = dialog.get_result()

        if new_name in self.subtextures.get(atlas_name, {}):
            self.showError(f"A subtexture named '{new_name}' already exists!")
            return

        self.subtextures[atlas_name][new_name] = self.subtextures[atlas_name].pop(old_name)

        for _, info in self.pending_additions.items():
            additions = info.get("additions", [])
            for a in additions:
                if a.get("name") == old_name:
                    a["name"] = new_name

        dcx_file = Path(atlas_item.data(Qt.UserRole+1)).name

        repls = self.pending_replacements.get(dcx_file, {}).get(atlas_name, {})
        if old_name in repls:
            repls[new_name] = repls.pop(old_name)

        sub_item.setText(new_name)
        sub_item.setData(Qt.UserRole, new_name)

        self.showSubtexture(sub_item)

    def revertSubtexture(self, sub_item):
        atlas_item = self.atlas_list.currentItem()
        if not atlas_item or not sub_item:
            return

        atlas_name = atlas_item.data(Qt.UserRole)
        dcx_file = Path(atlas_item.data(Qt.UserRole+1)).name
        sub_name = sub_item.data(Qt.UserRole)

        repls_for_file = self.pending_replacements.get(dcx_file)
        if not repls_for_file:
            return

        atlas_repls = repls_for_file.get(atlas_name)
        if not atlas_repls or sub_name not in atlas_repls:
            return

        del atlas_repls[sub_name]

        if not atlas_repls:
            del repls_for_file[atlas_name]
        if not repls_for_file:
            del self.pending_replacements[dcx_file]

        self.rebuildAtlas(atlas_name, dcx_file)
        sub_item.setForeground(Qt.white)

        items = [self.subtexture_list.item(i) for i in range(self.subtexture_list.count())]
        if all(self.isModified(dcx_file, atlas_name, item.data(Qt.UserRole)) == Modified.FALSE for item in items):
            atlas_item.setForeground(Qt.white)

        self.showSubtexture(sub_item)

    def addIcon(self):
        if self.atlas_list.count() == 0:
            self.showError('No atlases loaded!')
            return

        atlas_item = self.atlas_list.currentItem()
        if not atlas_item:
            self.showError('No atlas loaded!')
            return

        atlas_name = atlas_item.data(Qt.UserRole)
        dcx_file = Path(atlas_item.data(Qt.UserRole+1)).name

        subs = self.subtextures.get(atlas_name, {})
        if not subs:
            self.showError("This atlas isn't mapped, sorry!")
            return

        img_path = Path(QFileDialog.getOpenFileName(self, "Select Image", "", "Image Files (*.png *.dds *.jpg *.webm *.jpeg);;All Files (*.*)")[0])

        if not img_path or img_path == BLANK_PATH:
            return

        dialog = TextureNamePrompt()
        if not dialog.exec():
            return

        name, half = dialog.get_result()

        if name in subs:
            self.showError("An icon of this name already exists!")
            return

        img = Image.open(img_path).convert('RGBA')
        w, h = img.size

        atlas_img = self.getPilImage(atlas_name)

        padding = 2
        used_rects = [(st["x"] - padding, st["y"] - padding, st["x"] + st["width"] + padding, st["y"] + st["height"] + padding) for st in subs.values()]

        pos = Functions.getFreeSpace(atlas_img.size, used_rects, w, h, padding=padding)

        if pos:
            x, y = pos
        else:
            x = 0
            y = atlas_img.size[1] + padding

        sub = {
            'img': img,
            'name': name,
            'parent': atlas_name,
            'x': str(x),
            'y': str(y),
            'width': str(w),
            'height': str(h),
            'half': str(int(half))
        }

        self.pending_additions.setdefault(dcx_file, {
            "data": self.LAYOUT_FILES.get(dcx_file),
            "additions": [],
            "output": dcx_file.replace('.tpf', '.sblytbnd')
        })

        self.pending_additions[dcx_file]["additions"].append(sub)

        self.subtextures.setdefault(atlas_name, {})[name] = {'x': x, 'y': y, 'width': w, 'height': h, 'blank': False}

        self.rebuildAtlas(atlas_name, dcx_file)
        self.showAtlas(atlas_item)
            
    def showError(self, text, title="Error", _type=QMessageBox.Critical):
        """Error popup with specified text"""
        msg = QMessageBox()
        msg.setIcon(_type)
        msg.setWindowTitle(title) 
        msg.setText(text) 
        msg.exec() 

    def showQuery(self, title, text):
        return QMessageBox.question(self, title, text, QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
    
    def showSelectOptions(self, title, text, options):
        choice, ok = QInputDialog.getItem(self, title, text, options, 0, False)
        return ok, choice

    def clear(self):
        """Completely reset the window."""
        self.setWindowTitle("DSIE")
        self.atlas_list.clear()
        self.subtexture_list.clear()
        self.subtextures = {}
        self.atlases = {}
        self.current_crop = None
        self.current_atlas = None
        self.thumbnail_cache = {}
        self.pending_additions = {}
        self.pending_replacements = {}
        self.RESOLUTIONS = {}
        self.preview_label.setText("Select an atlas or subtexture")
        self.info_label.setText("Image info will appear here")

    def checkOodleDLL(self):
        """Find the oodle dll, or prompt for its location"""
        target = self.project_dir / "oo2core_6_win64.dll"

        try:
            oodle.LOAD_DLL(target)
        except oodle.MissingOodleDLLError:
            try:
                dll = oodle.LOAD_DLL() # no args, checks default paths
                shutil.copy(dll, target)
                print("DEBUG:: oodle dll found in default paths and copied to DSIE")
                
            except oodle.MissingOodleDLLError:

                result = QMessageBox.question(self, "DLL Missing",
                                                    "Could not find oo2core_6_win64.dll within default paths.\n"
                                                    "DCX_KRAK compression will be unavailable without it.\n\n"
                                                    "Would you like to manually locate it?",
                                                    QMessageBox.Yes | QMessageBox.No,
                                                    QMessageBox.No)
                
                if result == QMessageBox.Yes:
                    dll = Path(QFileDialog.getOpenFileName(self, "Navigate to oo2core_6_win64.dll", "", "DLL Files (*.dll)")[0])
                    if dll and Path(dll).exists():
                        if dll.name != "oo2core_6_win64.dll":
                            QMessageBox.warning(self, "Warning", "This dll doesn't match the expected version.")
                            return
                        try:
                            oodle.LOAD_DLL(dll)
                            # Copy DLL next to the exe for future runs
                            shutil.copy(dll, target)
                            QMessageBox.information(self, "DLL Copied", f"{dll.name} has been copied to DSIE.\n"
                                                                        "Future runs will automatically use this DLL.")
                            
                        except Exception as e:
                            QMessageBox.critical(self, "Error", f"Failed to load DLL:\n{e}")

    def openDcxDialog(self, dirmode: bool = False):
        """Handles everything to do with loading files. If dirmode = True, loads every dcx/tpf in a directory."""    
        self.clear()
        self.checkOodleDLL()

        if not dirmode:
            file_path = Path(QFileDialog.getOpenFileName(self, "Select DCX file", "", "DCX Files (*.dcx);;TPF Files (*.tpf)")[0])
            if not file_path or file_path == BLANK_PATH:
                return
            files = [file_path] if file_path else []
        else:
            dir_path = Path(QFileDialog.getExistingDirectory(self, "Select Folder"))
            if not dir_path or dir_path == BLANK_PATH:
                return
            files = [f for pattern in ["*.tpf.dcx", "*.tpf", "*sblytbnd.dcx"] for f in dir_path.glob(pattern)]

        if not files:
            return

        str_path = str(files[0].parent if dirmode else files[0])
        self.setWindowTitle(f"DSIE - {str_path}")

        game = Functions.parseGameType(path=str_path) or Functions.gameTypeDialog()
        if not game:
            return
        self.game = Game(game)

        file_mappings = []
        if self.game.name == 'Nightreign':
            if not dirmode:
                files += [f for f in file_path.parent.glob("*.sblytbnd.dcx")]

            groups = defaultdict(lambda: {"h": {}, "l": {}})
            standalone = []

            for f in files:
                name = f.name

                if "_h." in name:
                    prefix = name.split("_h.")[0]
                    res = "h"
                elif "_l." in name:
                    prefix = name.split("_l.")[0]
                    res = "l"
                else:
                    standalone.append(f)
                    continue

                if "sblytbnd" in name:
                    groups[prefix][res]["layout"] = f
                elif ".tpf" in name:
                    groups[prefix][res]["tpf"] = f
                else:
                    standalone.append(f)

            for prefix, data in groups.items():
                available = []

                for res in ["h", "l"]:
                    if "tpf" in data[res]:
                        available.append(res)

                if not available:
                    continue

                if len(available) > 1:
                    ok, choice = self.showSelectOptions("Select Resolution", f"{prefix} has both high and low resolution. Which do you want?", available)
                    if not ok:
                        return
                else:
                    choice = available[0]

                tpf = data[choice].get("tpf")
                layout = data[choice].get("layout")

                if tpf and not layout and ('_common_' in Path(tpf).stem):
                    layout_path = QFileDialog.getOpenFileName(self, f"Select layout for {tpf.name}", str(tpf.parent), "Layout Files (*.sblytbnd.dcx)")[0]

                    if layout_path:
                        layout = Path(layout_path)
                    else:
                        self.showError("Layout file doesn't exist. Loading raw atlases instead.")

                if layout:
                    file_mappings.append({"file": tpf, "layout": layout})
                else:
                    file_mappings.append(tpf)
                
                self.RESOLUTIONS[prefix] = choice

            file_mappings.extend(standalone) # no layout

        elif self.game.name in ['Sekiro', 'Elden Ring']:
            for f in files:
                if 'sblytbnd' in str(f):
                    continue

                base_name = Functions.replaceTerms(f.stem, {'.tpf': ''})
                layout = None

                if "common" in f.stem:
                    try_lyt = f.parent / f"{base_name}.sblytbnd.dcx"

                    if try_lyt.exists():
                        layout = try_lyt
                    else:
                        layout = Path(QFileDialog.getOpenFileName(None, "Navigate to corresponding sblytbnd.dcx", "", "Layout Files (*.sblytbnd.dcx)")[0])

                        if not layout.exists():
                            self.showError("Layout file doesn't exist!")
                            return

                if layout:
                    file_mappings.append({"file": f, "layout": layout})
                else:
                    file_mappings.append(f)

                self.RESOLUTIONS[base_name] = "L" if "\\low\\" in str(f) else "H"
        else:
            file_mappings = files

        self.progress_dialog = QProgressDialog("Loading DCX...", None, 0, 100, self)
        self.progress_dialog.setWindowTitle("Loading")
        self.progress_dialog.setWindowModality(Qt.ApplicationModal)
        self.progress_dialog.setStyleSheet("QProgressDialog {padding:0px;margin:0px;}")
        self.progress_dialog.show()

        self.thread = QThread()
        self.worker = LoadWorker(file_mappings, self.game)
        self.worker.moveToThread(self.thread)

        self.worker.progress.connect(self.updateProgress)
        self.worker.finished.connect(self.loadDone)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.started.connect(self.worker.run)
        self.thread.start()

    def loadDone(self, atlases, subtextures, LOADED_DCX_FILES, LAYOUT_FILES):
        """Stuff to do on successful load of files."""
        self.progress_dialog.close()

        if not atlases:
            QMessageBox.critical(self, "Error", "Failed to load textures.")
            return

        self.atlases = atlases
        self.subtextures = subtextures
        self.LOADED_DCX_FILES = LOADED_DCX_FILES
        self.LAYOUT_FILES = LAYOUT_FILES

        self.atlas_list.clear()
        for name, _atlas in atlases.items():
            item = NaturalListItem(name)
            item.setData(Qt.UserRole, name) # original name
            item.setData(Qt.UserRole+1, _atlas['parent']) # parent file
            img_type = "Atlas" if len(self.subtextures.get(name, {})) > 0 else "Texture"
            item.setData(Qt.UserRole+2, img_type) # image type
            self.atlas_list.addItem(item)

        self.atlas_list.sortItems()
        self.toggleCustomNames() # simply update it just in case setting was on before load
        self.atlas_list.setCurrentRow(0)

    def runExtraction(self, tasks=None, mode=ExportMode.SUBTEXTURE):
        """Start the extract process for images."""
        output_dir = self.project_dir / "Output"

        ok, filetype = self.showSelectOptions('File Type', 'Would you like to export in PNG or DDS?', ['png', 'dds'])
        if not ok:
            return

        self.progress_dialog = QProgressDialog("Exporting...", "Cancel", 0, 100, self)
        self.progress_dialog.setWindowTitle("Exporting")
        self.progress_dialog.setWindowModality(Qt.ApplicationModal)
        self.progress_dialog.show()
        QApplication.processEvents()

        thread = QThread(self)
        worker = ExtractWorker(self.atlases, self.subtextures, output_dir, loader=self.getPilImage, tasks=tasks, mode=mode, filetype=filetype)
        worker.moveToThread(thread)

        self.Ethread = thread
        self.Eworker = worker
        self.progress_dialog.canceled.connect(self.Eworker.interrupt)

        worker.progress.connect(self.updateProgress)
        worker.finished.connect(self.extractionDone)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        thread.started.connect(worker.run)
        thread.start()

    def updateProgress(self, percent, message):
        """Updates the loading dialog values."""
        self.progress_dialog.setValue(percent)
        self.progress_dialog.setLabelText(message)

    def extractionDone(self, success=True):
        """Stuff to do after extraction finishes"""
        self.progress_dialog.close()
        if success:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Information)
            msg.setWindowTitle("Saved")
            msg.setText(f"Export saved to {self.project_dir / "Output"}")
            _open = QPushButton("Open Folder")
            msg.addButton(_open, QMessageBox.ActionRole)
            msg.addButton(QMessageBox.Ok)
            _open.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.project_dir / "Output"))))
            msg.exec()
        else:
            QMessageBox.critical(self, "Error", f"Failed to find subtextures")

    def toggleCustomNames(self):
        """Replaces displaying text for QListWidgetItems with the mapped ones whilst retaining the original in UserRole"""

        def restoreNames(widget: QListWidget):
            for idx in range(widget.count()):
                item = widget.item(idx)
                item.setText(item.data(Qt.UserRole))

        if self.btn_useCustomNames.isChecked():
            for idx in range(self.atlas_list.count()):
                item = self.atlas_list.item(idx)
                text = item.text()
                if self.game.name == 'Dark Souls 2': # special handling due to weird naming system
                    text = text[text.rfind('_')+1:]

                name = Maps.AtlasNames[self.game.name].get(text, None) or item.text()
                item.setText(name)
            
            for idx in range(self.subtexture_list.count()):
                item = self.subtexture_list.item(idx)
                text = item.text()

                _, *pieces = text.split('_')
                try:
                    id = pieces[-1]
                    _type = pieces[0]
                    name = Maps.TextureNames[self.game.name].get(_type, {}).get(id.lstrip('0'), None) or text
                except IndexError:
                    name = text

                item.setText(name)

        else:
            restoreNames(self.atlas_list)
            restoreNames(self.subtexture_list)

    def promptAlphaThreshold(self):
        num, ok = QInputDialog.getInt(None, "Prompt", "Enter new Alpha Threshold:", 10, 0, 255, 1)
        if not ok:
            return
        self.alphaThreshold = num
        self.btn_alphaThreshold.setText(f"Alpha Threshold = {num}")
        self.showAtlas(self.atlas_list.currentItem())

    def openSearchWindow(self):
        """Creates a SearchWindow instance and then handles the returned settings and string."""
        def handle_search(text, atlasMode):
            if atlasMode:
                widget = self.atlas_list
            else:
                widget = self.subtexture_list

            if not widget.count() > 0:
                self.showError('No Textures are loaded.')
                return

            results = widget.findItems(text, Qt.MatchContains)
            if results:
                item = results[0]
                item.setSelected(True)
                widget.setCurrentItem(item)
                widget.scrollToItem(item)
            else:
                self.showError('No results found!')

        self.searchInstance = SearchWindow()
        self.searchInstance.results.connect(handle_search)
        self.searchInstance.show()

    def resolveSubtexture(self, atlas_name, sub_name, atlas_img):
        """Return subtexture rect from either layout or grid system."""

        st = self.subtextures.get(atlas_name, {}).get(sub_name)
        if st:
            return st

        texmap = Maps.TextureDimensions[self.game.name]
        dimensions = texmap.get(atlas_name)

        if not dimensions:
            return None

        tile_w = dimensions['width']
        tile_h = dimensions['height']

        atlas_w, _ = atlas_img.size
        tiles_per_row = atlas_w // tile_w

        try:
            idx = int(sub_name)
        except:
            return None

        row = idx // tiles_per_row
        col = idx % tiles_per_row

        return {
            "x": col * tile_w,
            "y": row * tile_h,
            "width": tile_w,
            "height": tile_h}

    def queueReplacement(self, dcx_file: Path, atlas_item, sub_item, img_path: Path):
        atlas_name = atlas_item.data(Qt.UserRole)
        dcx_file = Path(dcx_file).name
        sub_name = sub_item.data(Qt.UserRole) if sub_item else None

        try:
            new_img = Image.open(img_path).convert("RGBA")
        except UnidentifiedImageError:
            self.showError("Selected file is not an image supported by PIL.")
            return

        if sub_name:
            atlas_img = self.getPilImage(atlas_name)
            st = self.resolveSubtexture(atlas_name, sub_name, atlas_img)

            if not st:
                self.showError(f"Could not resolve subtexture: {sub_name}")
                return

            new_img = new_img.resize((st["width"], st["height"]), Image.Resampling.LANCZOS)

        self.pending_replacements.setdefault(dcx_file, {}).setdefault(atlas_name, {})
        self.pending_replacements[dcx_file][atlas_name][sub_name] = new_img

        self.rebuildAtlas(atlas_name, dcx_file)

        atlas_item.setForeground(Qt.yellow)
        if sub_item:
            sub_item.setForeground(Qt.yellow)
            self.showSubtexture(sub_item)
        else:
            self.showAtlas(atlas_item)

    def registerReplacement(self):
        """Prompt the user for an image, then add it to the replacement queue with the currently selected texture as the target."""
        if self.atlas_list.count() == 0:
            self.showError('No atlases loaded!')
            return
        
        atlas = self.atlas_list.currentItem()
        sub = self.subtexture_list.currentItem()
        dcx_file = atlas.data(Qt.UserRole+1)

        if not atlas:
            self.showError('No atlas loaded!')
            return

        img_path = Path(QFileDialog.getOpenFileName(self, "Select Image", "", "Image Files (*.png *.dds *.jpg *.webm *.jpeg);;All Files (*.*)")[0])
        if not img_path or img_path == BLANK_PATH:
            return
        
        self.queueReplacement(Path(dcx_file), atlas, sub, Path(img_path))

    def applyChanges(self):
        """Start replacement from File menu and create popup."""
        if not self.pending_replacements and not self.pending_additions:
            QMessageBox.information(self, "Info", "No actions queued.")
            return
    
        self.replace_dialog = QProgressDialog("Applying changes...", None, 0, 0, self)
        self.replace_dialog.setWindowTitle("Processing")
        self.replace_dialog.setWindowModality(Qt.ApplicationModal)
        self.replace_dialog.setCancelButton(None)
        self.replace_dialog.setMinimumDuration(0)
        self.replace_dialog.setMinimumWidth(300)
        self.replace_dialog.show()
        self.replace_dialog.setStyleSheet("""QLabel {qproperty-alignment: AlignCenter;} QProgressBar {text-align: center;}""")

        self.r_thread = QThread()
        self.r_worker = ReplaceWorker(self.pending_replacements, self.pending_additions, self.subtextures, self.LOADED_DCX_FILES, self.LAYOUT_FILES, self.getPilImage, self.project_dir, self.game, self.RESOLUTIONS)
        self.r_worker.moveToThread(self.r_thread)
        self.r_thread.started.connect(self.r_worker.run)

        self.r_worker.finished.connect(self.r_thread.quit)
        self.r_worker.finished.connect(self.replaceDone)
        self.r_worker.finished.connect(self.r_worker.deleteLater)
        self.r_thread.finished.connect(self.r_thread.deleteLater)
        
        self.r_thread.start()

    def replaceDone(self, success: bool, msg: str):
        """Triggered on completion of tpf/dcx export."""
        self.replace_dialog.close()
        if success:
            self.extractionDone(True)
            self.pending_replacements.clear()
        else:
            self.showError(msg)

    def pil2Qpixmap(self, pil_img, max_size=(600, 400)):
        """Convert PIL Image to QPixmap without destroying the aspect ratio lol"""
        data = pil_img.tobytes("raw", "RGBA")
        qimg = QImage(data, pil_img.width, pil_img.height, QImage.Format_RGBA8888)
        pixmap = QPixmap.fromImage(qimg)

        return pixmap.scaled(max_size[0], max_size[1], Qt.KeepAspectRatio, Qt.SmoothTransformation)
    
    def getPngSize(self, pil_img):
        """Simulate a png export to get file size."""
        buf = BytesIO()
        pil_img.save(buf, format="PNG")
        return len(buf.getvalue())

    def formatImageInfo(self, name, pil_img, coords='None', img_type="Atlas"):
        """Properly format information about the selected preview to display."""
        def formatSize(bytes_val):
            kb = bytes_val / 1024
            if kb < 1024:
                return f"{kb:.1f} KB"
            return f"{kb / 1024:.2f} MB"
        
        width, height = pil_img.size
        size_uc = formatSize(width * height * len(pil_img.getbands()))
        size_c = formatSize(self.getPngSize(pil_img)) if self.btn_calcImageSize.isChecked() else "???"
        return (
            f"<b>Type:</b> {img_type}<br>"
            f"<b>Name:</b> {name}<br>"
            f"<b>Coordinates:</b> {coords}<br>"
            f"<b>Dimensions:</b> {width} × {height}px<br>"
            f"<b>Uncompressed Size:</b> {size_uc}<br>"
            f"<b>Compressed Size:</b> {size_c}"
        )

    def rebuildAtlas(self, atlas_name, dcx_file):
        """Reconstruct the atlas with its changes"""
        #print(self.pending_additions, self.pending_replacements)
        base_img = self.getBaseImage(atlas_name)

        additions = (self.pending_additions.get(dcx_file, {}).get("additions", []))

        for add in additions:
            if add.get("parent") != atlas_name:
                continue

            img = add["img"]
            x = int(add["x"])
            y = int(add["y"])

            if y + img.height > base_img.height:
                new_height = y + img.height
                new_img = Image.new("RGBA", (base_img.width, new_height), (0, 0, 0, 0))
                new_img.paste(base_img, (0, 0))
                base_img = new_img

            base_img.paste(img, (x, y))

        atlas_repls = (self.pending_replacements.get(dcx_file, {}).get(atlas_name, {}))

        for sub_name, img in atlas_repls.items():
            if sub_name is None: # full atlas replacement
                base_img = img.copy()
                continue

            st = self.resolveSubtexture(atlas_name, sub_name, base_img)
            if not st:
                continue

            base_img.paste(img, (st["x"], st["y"]))

        self.thumbnail_cache[atlas_name] = base_img

    def getBaseImage(self, atlas_name):
        """Always returns the original atlas image"""
        texture = self.atlases[atlas_name]['texture']
        with BytesIO(texture.data) as dds_buffer:
            return Image.open(dds_buffer).convert("RGBA")

    def getPilImage(self, atlas_name, createDebug=False):
        """Returns rendered preview (rebuild if needed)"""
        
        if atlas_name not in self.thumbnail_cache:
            atlas_item = self.atlas_list.currentItem()
            if atlas_item:
                dcx_file = Path(atlas_item.data(Qt.UserRole+1)).name
                self.rebuildAtlas(atlas_name, dcx_file)

        img = self.thumbnail_cache.get(atlas_name)

        if img is None:
            img = self.getBaseImage(atlas_name)

        if createDebug:
            img = Functions.createDebugGrid(img, self.subtextures[atlas_name])

        if self.alphaThreshold > 0:
            img = Functions.cleanByAlpha(img, threshold=self.alphaThreshold)

        return img

    def isModified(self, dcx_file, atlas_name, sub_name=None):
        """Returns True if subtexture has been modified, for recoloring its entry."""
        if sub_name in self.pending_replacements.get(dcx_file, {}).get(atlas_name, {}):
            return Modified.REPLACED
        if any(sub_name == i['name'] for i in self.pending_additions.get(dcx_file, {}).get('additions', [])):
            return Modified.ADDED
        return Modified.FALSE

    def showAtlas(self, current):
        """Display the selected atlas, and load all subtextures to the list."""
        if not current:
            return
        atlas_name = current.data(Qt.UserRole)
        dcx_file = Path(current.data(Qt.UserRole+1)).name
        self.current_atlas = atlas_name
        self.current_crop = None
        atlas_modified = False

        atlas_img = self.getPilImage(atlas_name, createDebug=self.btn_atlasGrid.isChecked())
        preview_img = atlas_img.copy()
        preview_img.thumbnail((600, 400), Image.Resampling.LANCZOS)
        pixmap = self.pil2Qpixmap(preview_img)
        self.preview_label.setPixmap(pixmap)

        # Load subtextures
        self.subtexture_list.blockSignals(True)
        self.subtexture_list.clear()
        for key, val in self.subtextures.get(atlas_name, {}).items():
            if self.btn_hideBlankIcons.isChecked() and val['blank']:
                continue

            item = NaturalListItem(key)
            item.setData(Qt.UserRole, key)

            modify = self.isModified(dcx_file, atlas_name, key)
            if modify == Modified.REPLACED:
                item.setForeground(Qt.yellow)
                atlas_modified = True
            if modify == Modified.ADDED:
                item.setForeground(Qt.green)
                atlas_modified = True

            self.subtexture_list.addItem(item)
        
        current.setForeground(Qt.yellow if atlas_modified else Qt.white)
        self.subtexture_list.blockSignals(False)
        self.subtexture_list.sortItems()

        self.info_label.setText(self.formatImageInfo(atlas_name, atlas_img, img_type=current.data(Qt.UserRole+2)))
        self.toggleCustomNames() # just to update it

    def showSubtexture(self, current):
        """Display a preview of the selected subtexture."""
        if not current or not self.current_atlas:
            return
        
        try:
            name = current.data(Qt.UserRole)
            st = self.subtextures[self.current_atlas][name]
            atlas_img = self.getPilImage(self.current_atlas)
        except KeyError:
            self.subtexture_list.blockSignals(False)
            return

        cropped = atlas_img.crop((st["x"], st["y"], st["x"] + st["width"], st["y"] + st["height"]))
        cropped.thumbnail((600, 400), Image.Resampling.LANCZOS)
        pixmap = self.pil2Qpixmap(cropped)

        self.preview_label.setPixmap(pixmap)
        self.current_crop = cropped
        self.info_label.setText(self.formatImageInfo(name, cropped, (st['x'], st['y']), 'Subtexture'))

    def saveSelection(self):
        """Save current subtexture or whole atlas"""
        if not self.current_atlas:
            QMessageBox.warning(self, "Warning", "No atlas selected.")
            return

        if self.current_crop is not None and self.subtexture_list.currentItem(): # Subtexture selected
            key = self.subtexture_list.currentItem().data(Qt.UserRole)
            self.runExtraction(tasks=[(self.current_atlas, key)])

        else: # No subtexture selected, export the full atlas   
            img_type = self.atlas_list.currentItem().data(Qt.UserRole+2)
            if img_type == "Atlas":
                ok, choice = self.showSelectOptions("Select Export", f"The currently selected texture is an atlas.\nWould you like to export the whole image, " \
                                                    "or its subtextures?", ["Full Atlas", "All Subtextures"])
                
                if not ok:
                    return
                if choice == "All Subtextures":
                    self.saveAll()
                    return

            out_path = self.project_dir / "Output" / ".Atlases"
            out_path.mkdir(parents=True, exist_ok=True)

            gridOverlay = self.btn_atlasGrid.isChecked()
            if gridOverlay:
                answer = self.showQuery('Export', 'You currently have the Grid Overlay enabled, do you want to keep it in the image for this export?')
                if answer == QMessageBox.Cancel:
                    return
                
                elif answer == QMessageBox.No:
                    gridOverlay = False

            self.runExtraction(tasks=[(self.current_atlas, None)], mode=ExportMode.ATLAS)

    def saveAll(self):
        """Export all subtextures from the currently selected atlas"""
        if not self.current_atlas:
            QMessageBox.warning(self, "Warning", "No atlas selected.")
            return

        tasks = [(self.current_atlas, st) for st in self.subtextures.get(self.current_atlas, [])]
        if not tasks:
            QMessageBox.information(self, "Info", f"No subtextures found for {self.current_atlas}.")
            return

        self.runExtraction(tasks=tasks)

    def dumpTextures(self, mode=ExportMode.SUBTEXTURE):
        """Export all atlases or subtextures. Subtextures go into directories for their atlases"""
        self.runExtraction(mode=mode)

def getIcon(base_path):
    if getattr(sys, 'frozen', False):
        return QIcon(str(Path(sys.executable).parent / 'icon.ico'))
    else:
        return QIcon(str(base_path / 'icon.ico'))

def main():
    app = QApplication(sys.argv)
    base_path = Path(sys.argv[0]).parent
    app.setWindowIcon(getIcon(base_path))
    window = MainWindow(project_dir=base_path)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

# nuitka --standalone --onefile --windows-console-mode=disable --enable-plugin=pyside6 --windows-icon-from-ico=icon.ico --include-data-file=icon.ico=icon.ico --include-data-file=soulstruct\base\textures\texconv.exe=soulstruct\base\textures\texconv.exe --include-module=constrata --include-module=soulstruct --msvc=latest --lto=yes DSIE.py
# pyinstaller DSIE.py --noconsole --icon=icon.ico --add-data "icon.ico;." --add-binary "soulstruct/base/textures/texconv.exe;soulstruct/base/textures" --collect-data soulstruct