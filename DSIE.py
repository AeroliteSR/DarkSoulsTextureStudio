from __future__ import annotations
import sys, os, io, shutil
import numpy as np
from io import BytesIO
import xml.etree.ElementTree as ET
from pathlib import Path
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QCheckBox,
QLabel, QHBoxLayout, QFileDialog, QPushButton, QMessageBox, QSplitter, QProgressDialog, QInputDialog, QLineEdit)
from PySide6.QtGui import QPixmap, QImage, QIcon, QDesktopServices, QAction
from PySide6.QtCore import Qt, QObject, QThread, QUrl, Signal
from PIL import Image, ImageDraw
from soulstruct.containers import tpf
from soulstruct.dcx import core, oodle
from GameInfo import Maps
from collections import defaultdict

class Functions():
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
    def createDebugGrid(image, tiles_per_column, tiles_per_row, tile_width, tile_height):
        """Outputs a png with grid lines for debugging"""
        debug = image.copy()
        draw = ImageDraw.Draw(debug)

        for row in range(tiles_per_column):
            for col in range(tiles_per_row):
                x = col * tile_width
                y = row * tile_height
                draw.rectangle([x, y, x + tile_width, y + tile_height], outline="red", width=1)

        debug.save("debug_grid.png")

    @staticmethod
    def loadTextures(dcx_path, layout_path):
        """Load textures from the TPF.DCX and parse layout XML
        This function is no longer used"""
        layout_xml = Functions.getLayoutData(layout_path)
        root = ET.fromstring(layout_xml, parser=None) # SET TO PARSER IF USED

        tpfdcx = tpf.TPF.from_path(dcx_path)
        textures_dict = {texture.stem: texture for texture in tpfdcx.textures}

        atlases = {}
        subtextures = {}

        for texture_atlas in root.findall("TextureAtlas"):
            filepath = texture_atlas.get("imagePath")
            filename = Path(filepath).stem

            if filename not in textures_dict:
                print(f"{filename} not found in TPF textures, skipping.")
                continue

            # Convert DDS to PIL Image
            texture = textures_dict[filename]
            with io.BytesIO(texture.data) as dds_buffer:
                dds_buffer.seek(0)
                atlas_img = Image.open(dds_buffer).convert("RGBA")

            atlases[filename] = atlas_img
            subtextures[filename] = []

            for subtexture in texture_atlas.findall("SubTexture"):
                subtextures[filename].append({
                    "name": subtexture.get("name"),
                    "x": int(subtexture.get("x")),
                    "y": int(subtexture.get("y")),
                    "width": int(subtexture.get("width")),
                    "height": int(subtexture.get("height")),
                })

        return atlases, subtextures

class LoadWorker(QObject):
    progress = Signal(int, str)   # percent, message
    finished = Signal(dict, dict)  # atlases, subtextures

    def __init__(self, file_mappings, game_type):
        super().__init__()
        self.file_mappings = file_mappings
        self.game = game_type

    def run(self):
        if self.game in ['Dark Souls 1', 'Dark Souls 2', 'Dark Souls 3',]:
            self.processOld()
        else: # sblyt is used
            self.processModern()

    def generateTextDict(self, dcx_path, percent):
        textures_dict: dict = {}
        self.progress.emit(percent, f"Unpacking {dcx_path.stem}...")
        if dcx_path.is_dir():
            for file in os.listdir(dcx_path):
                if file.endswith('tpf.dcx') or file.endswith('.tpf'):
                    path = Path(dcx_path) / file
                    tpfdcx = tpf.TPF(path)
                    for texture in tpfdcx.textures:
                        textures_dict[texture.stem] = texture
        else:
            tpfdcx = tpf.TPF(dcx_path)
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
                    total_atlases = len(atlas_nodes)

                    if total_atlases == 0:
                        self.progress.emit(100, "No atlases found")
                        return

                    for texture_atlas in atlas_nodes:
                        filepath = texture_atlas.get("imagePath")
                        filename = Path(filepath).stem

                        if filename not in textures_dict:
                            self.progress.emit(int(f_idx / total_files * 100), f"{filename} not found, skipping.")
                            continue

                        atlases[filename] = textures_dict[filename]  # store raw texture
                        subtextures[filename] = {}

                        for sub in texture_atlas.findall("SubTexture"):
                            subtextures[filename][sub.get("name").replace('.png', '')] = {
                                "x": int(sub.get("x")),
                                "y": int(sub.get("y")),
                                "width": int(sub.get("width")),
                                "height": int(sub.get("height"))}

                elif isinstance(file, Path):
                    textures_dict: dict = self.generateTextDict(file, percent)
                    # add any textures that were not included in the layout
                    for name, texture in textures_dict.items():
                        if name not in atlases:
                            atlases[name] = texture
                            subtextures[name] = {}  # no layout info since single textures go to atlases

            self.finished.emit(atlases, subtextures)
            self.progress.emit(100, 'Successfully loaded all files!')

        except IndentationError as e:
            print(e)
            self.progress.emit(0, f"Error: {e}")
            self.finished.emit({}, {})

    def processOld(self):  
        try:
            atlases = {}
            subtextures = {}
            total_files = len(self.file_mappings)

            for f_idx, file in enumerate(self.file_mappings, 1):
                percent = int(f_idx / total_files * 100 - 1)
                textures_dict: dict = self.generateTextDict(file, percent)

                for name, texture in textures_dict.items():
                    atlases[name] = texture
                    subtextures[name] = {}
                    dds = texture.get_dds()
                    image = Image.open(BytesIO(dds.to_bytes())).convert("RGBA")

                    texmap = Maps.TextureDimensions[self.game]
                    dimensions = texmap.get(name, None)
                    if dimensions:
                        tile_width, tile_height = dimensions['width'], dimensions['height']

                        atlas_width, atlas_height = dds.header.width, dds.header.height
                        tiles_per_row = atlas_width // tile_width
                        tiles_per_column = atlas_height // tile_height
                        #Functions.createDebugGrid(image, tiles_per_column, tiles_per_row, tile_width, tile_height)

                        total_tiles = tiles_per_row * tiles_per_column

                        for idx in range(total_tiles):
                            row = idx // tiles_per_row
                            col = idx % tiles_per_row
                            x = col * tile_width
                            y = row * tile_height

                            tile = image.crop((x, y, x + tile_width, y + tile_height))
                            alpha = np.array(tile.getchannel("A"))
                            opacity_ratio = np.count_nonzero(alpha) / alpha.size
                            if opacity_ratio < 0.01:
                                continue # skip saving subtexture if it's blank

                            subtextures[name][str(idx)] = {
                                "x": x,
                                "y": y,
                                "width": tile_width,
                                "height": tile_height}

                        self.progress.emit(percent, f"Processed {name}")

            self.finished.emit(atlases, subtextures)

        except Exception as e:
            print(e)
            self.progress.emit(0, f"Error: {e}")
            self.finished.emit({}, {})

class ExtractWorker(QObject):
    progress = Signal(int, str) # percent, message
    finished = Signal(bool) # success

    def __init__(self, atlases, subtextures, output_dir, loader, tasks=None, mode='S'):
        super().__init__()
        self.atlases = atlases
        self.subtextures = subtextures
        self.output_dir = output_dir
        self.pilLoader = loader
        self.tasks = tasks if tasks is not None else []
        self.mode = mode
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
        if not self.tasks:
            if self.mode == 'A':
                if not self.atlases:
                    self.finished.emit(False)
                    return

                for atlas_name in self.atlases:
                    self.tasks.append((atlas_name, None))

            elif self.mode == 'S':
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

            atlas_img = self.pilLoader(atlas_name=atlas_name)
            percent = int(i / total * 100)

            if self.mode == 'A':
                out_path = self.output_dir / '_Atlases'
                filename = atlas_name
                message = f"Exported atlas: {atlas_name}"

            elif self.mode == 'S':
                out_path = self.output_dir / atlas_name
                filename = st['name']
                message = f"Exported {st['name']} from {atlas_name}"
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

class MainWindow(QMainWindow):
    def __init__(self, project_dir):
        super().__init__()
        self.project_dir = project_dir
        self.useCustomNames: bool = False

        self.setWindowTitle("DSIE")
        self.setGeometry(100, 100, 1100, 700)
        self.createMenu()

        self.current_crop = None
        self.current_atlas = None
        self.thumbnail_cache = {}

        container = QWidget()
        layout = QHBoxLayout(container)
        splitter = QSplitter(Qt.Horizontal)

        self.atlas_list = QListWidget()
        self.atlas_list.itemClicked.connect(self.showAtlas)
        splitter.addWidget(self.atlas_list)

        self.subtexture_list = QListWidget()
        self.subtexture_list.itemClicked.connect(self.showSubtexture)
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

        self.save_all_button = QPushButton("Export All Subtextures From Atlas")
        self.save_all_button.clicked.connect(self.saveAll)
        right_layout.addWidget(self.save_all_button)

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
        self.file_menu.addAction(createAction("Dump All Atlases", lambda: self.dumpTextures(mode='A')))
        self.file_menu.addAction(createAction("Dump All Subtextures", lambda: self.dumpTextures(mode='S')))
        self.file_menu.addSeparator()
        self.file_menu.addAction(createAction("Exit", self.close))

        self.settings_menu = menu.addMenu("Settings")
        self.toggle_action = QAction("Use Names", self)
        self.toggle_action.setCheckable(True)
        self.toggle_action.setChecked(self.useCustomNames)
        self.toggle_action.toggled.connect(self.toggleCustomNames)
        self.settings_menu.addAction(self.toggle_action)

        self.searchButton = menu.addAction(createAction("Search", self.openSearchWindow))

        self.help_menu = menu.addMenu("Help")
        self.help_menu.addAction(createAction("About", self.showAbout))

    def showError(self, text):
        """Error popup with specified text"""
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle("Error") 
        msg.setText(text) 
        msg.exec() 

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
        self.preview_label.setText("Select an atlas or subtexture")
        self.info_label.setText("Image info will appear here")

    def checkOodleDLL(self):
        """Find the oodle dll, or prompt for its location"""
        target = self.project_dir / "oo2core_6_win64.dll"

        try:
            oodle.LOAD_DLL(target)
        except oodle.MissingOodleDLLError:
            result = QMessageBox.question(
                    self,
                    "DLL Missing",
                    "Could not find oo2core_6_win64.dll within default game paths.\n"
                    "Textures will not be loaded without it.\n\n"
                    "Would you like to manually locate it?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No)
            
            if result == QMessageBox.Yes:
                dll = Path(QFileDialog.getOpenFileName(self, "Navigate to oo2core_6_win64.dll", "", "DLL Files (*.dll)")[0])
                if dll and Path(dll).exists():
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
            files = [file_path] if file_path else []
        else:
            dir_path = Path(QFileDialog.getExistingDirectory(self, "Select Folder"))
            if not dir_path or dir_path == Path('.'):
                return
            files = [f for pattern in ["*.tpf.dcx", "*.tpf", "*sblytbnd.dcx"] for f in dir_path.glob(pattern)]

        if not files:
            return

        str_path = str(files[0].parent if dirmode else files[0])
        self.setWindowTitle(f"DSIE - {str_path}")

        self.game = Functions.parseGameType(path=str_path) or Functions.gameTypeDialog()
        if not self.game:
            return

        file_mappings = []
        if self.game == 'Nightreign':
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
                    choice, ok = QInputDialog.getItem(self, "Select Resolution", f"{prefix} has both high and low resolution. Which do you want?", available, 0, False)
                    if not ok:
                        return
                else:
                    choice = available[0]

                tpf = data[choice].get("tpf")
                layout = data[choice].get("layout")

                if tpf and not layout:
                    layout_path = QFileDialog.getOpenFileName(self, f"Select layout for {tpf.name}", str(tpf.parent), "Layout Files (*.sblytbnd.dcx)")[0]

                    if layout_path:
                        layout = Path(layout_path)
                    else:
                        self.showError("Layout file doesn't exist!")
                        return

                if layout:
                    file_mappings.append({"file": tpf, "layout": layout})
                else:
                    file_mappings.append(tpf)

            file_mappings.extend(standalone) # no layout

        elif self.game in ['Sekiro', 'Elden Ring']:
            for f in files:
                if 'sblytbnd' in str(f):
                    continue

                layout = None
                if "common" in f.stem:
                    base_name = Functions.replaceTerms(f.stem, {'.tpf': ''})

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

    def loadDone(self, atlases, subtextures):
        """Stuff to do on successful load of files."""
        self.progress_dialog.close()

        if not atlases:
            QMessageBox.critical(self, "Error", "Failed to load textures.")
            return

        self.atlases = atlases
        self.subtextures = subtextures

        self.atlas_list.clear()
        for key in atlases.keys():
            item = QListWidgetItem(key)
            item.setData(Qt.UserRole, key)
            self.atlas_list.addItem(item)

        self.subtexture_list.clear()
        self.preview_label.setText("Select an atlas or subtexture")
        self.info_label.setText("Image info will appear here")

    def runExtraction(self, tasks=None, mode='S'):
        output_dir = self.project_dir / "Output"

        self.progress_dialog = QProgressDialog("Exporting...", "Cancel", 0, 100, self)
        self.progress_dialog.setWindowTitle("Exporting")
        self.progress_dialog.setWindowModality(Qt.ApplicationModal)
        self.progress_dialog.show()

        thread = QThread(self)
        worker = ExtractWorker(self.atlases, self.subtextures, output_dir, loader=self.getPilImage, tasks=tasks, mode=mode)
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

    def showAbout(self):
        """Show about popup."""
        QMessageBox.information(self, "About", "Made by <a href='https://linktr.ee/aerolitesr'>Aero</a> :><br><br>")

    def toggleCustomNames(self):
        """Replaces displaying text for QListWidgetItems with the mapped ones whilst retaining the original in UserRole"""

        def restoreNames(widget: QListWidget):
            for idx in range(widget.count()):
                item = widget.item(idx)
                item.setText(item.data(Qt.UserRole))

        self.useCustomNames = self.toggle_action.isChecked()
        
        if self.useCustomNames:
            for idx in range(self.atlas_list.count()):
                item = self.atlas_list.item(idx)
                text = item.text()
                if self.game == 'Dark Souls 2': # special handling due to weird naming system
                    text = text[text.rfind('_')+1:]

                name = Maps.AtlasNames[self.game].get(text, None) or item.text()
                item.setText(name)
            
            for idx in range(self.subtexture_list.count()):
                item = self.subtexture_list.item(idx)
                text = item.text()

                _, *pieces = text.split('_')
                try:
                    id = pieces[-1]
                    _type = pieces[0]
                    name = Maps.TextureNames[self.game].get(_type, {}).get(id.lstrip('0'), None) or text
                except IndexError:
                    name = text

                item.setText(name)

        else:
            restoreNames(self.atlas_list)
            restoreNames(self.subtexture_list)

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

    def pil2Qpixmap(self, pil_img, max_size=(600, 400)):
        """Convert PIL Image to QPixmap without destroying the aspect ratio lol"""
        data = pil_img.tobytes("raw", "RGBA")
        qimg = QImage(data, pil_img.width, pil_img.height, QImage.Format_RGBA8888)
        pixmap = QPixmap.fromImage(qimg)

        return pixmap.scaled(max_size[0], max_size[1], Qt.KeepAspectRatio, Qt.SmoothTransformation)
    
    def getPngSize(self, pil_img):
        """Simulate a png export to get file size."""
        buf = io.BytesIO()
        pil_img.save(buf, format="PNG")
        return len(buf.getvalue())

    def formatImageInfo(self, name, pil_img, img_type="Atlas"):
        """Properly format information about the selected preview to display."""
        width, height = pil_img.size
        size_uc = len(pil_img.tobytes()) / 1024
        size_c = self.getPngSize(pil_img) / 1024
        return (
            f"<b>Type:</b> {img_type}<br>"
            f"<b>Name:</b> {name}<br>"
            f"<b>Dimensions:</b> {width} × {height}px<br>"
            f"<b>Uncompressed Size:</b> {size_uc:.1f} KB<br>"
            f"<b>Compressed Size:</b> {size_c:.1f} KB"
        )

    def getPilImage(self, atlas_name):
        """Load PIL image from TPF texture on-demand."""
        if atlas_name in self.thumbnail_cache:
            return self.thumbnail_cache[atlas_name]

        texture = self.atlases[atlas_name]
        with io.BytesIO(texture.data) as dds_buffer:
            img = Image.open(dds_buffer).convert("RGBA")
        self.thumbnail_cache[atlas_name] = img
        return img

    def showAtlas(self, current):
        """Display the selected atlas, and load all subtextures to the list."""
        if not current:
            return
        atlas_name = current.data(Qt.UserRole)
        self.current_atlas = atlas_name
        self.current_crop = None
        self.subtexture_list.clear()

        atlas_img = self.getPilImage(atlas_name)
        preview_img = atlas_img.copy()
        preview_img.thumbnail((600, 400), Image.Resampling.LANCZOS)
        pixmap = self.pil2Qpixmap(preview_img)
        self.preview_label.setPixmap(pixmap)

        self.info_label.setText(self.formatImageInfo(atlas_name, atlas_img, "Atlas"))
        # Load subtextures
        for key in self.subtextures.get(atlas_name, {}).keys():
            item = QListWidgetItem(key)
            item.setData(Qt.UserRole, key)
            self.subtexture_list.addItem(item)
        self.toggleCustomNames() # just to update it

    def showSubtexture(self, current):
        """Display a preview of the selected subtexture."""
        if not current or not self.current_atlas:
            return
        name = current.data(Qt.UserRole)
        st = self.subtextures[self.current_atlas][name]

        atlas_img = self.getPilImage(self.current_atlas)
        cropped = atlas_img.crop((st["x"], st["y"], st["x"] + st["width"], st["y"] + st["height"]))
        cropped.thumbnail((600, 400), Image.Resampling.LANCZOS)
        pixmap = self.pil2Qpixmap(cropped)

        self.preview_label.setPixmap(pixmap)
        self.current_crop = cropped
        self.info_label.setText(self.formatImageInfo(name, cropped, "Subtexture"))

    def saveSelection(self):
        """Save current subtexture or whole atlas"""
        if not self.current_atlas:
            QMessageBox.warning(self, "Warning", "No atlas selected.")
            return

        if self.current_crop is not None and self.subtexture_list.currentItem(): # Subtexture selected
            st = next(s for s in self.subtextures[self.current_atlas] if s["name"] == self.subtexture_list.currentItem().text())
            self.runExtraction(tasks=[(self.current_atlas, st)])

        else: # No subtexture selected, export the full atlas
            out_path = self.project_dir / "Output" /"_Atlases"
            out_path.mkdir(parents=True, exist_ok=True)
            atlas_img = self.getPilImage(self.current_atlas)
            atlas_img.save(out_path / f"{self.current_atlas}.png")
            self.extractionDone()

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

    def dumpTextures(self, mode='S'):
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

# nuitka --standalone --onefile --windows-console-mode=disable --enable-plugin=pyside6 --windows-icon-from-ico=icon.ico --include-data-file=icon.ico=icon.ico --msvc=latest --lto=yes DSIE.py
# pyinstaller DSIE.py --noconsole --icon=icon.ico --add-data "icon.ico;." --collect-data soulstruct