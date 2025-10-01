import sys
import io
import xml.etree.ElementTree as ET
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QListWidget, QLabel, QHBoxLayout, QFileDialog,
    QPushButton, QMessageBox, QSplitter, QAction, QProgressDialog)
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt, QObject, pyqtSignal, QThread
from PIL import Image
from soulstruct.containers import tpf
from soulstruct.dcx import core

class Functions():
    def getLayoutData(dcx_path):
        with open(dcx_path, "rb") as f:
            decompressed_bytes, _ = core.decompress(f)
            start_index = decompressed_bytes.find(b"<")
            xml_bytes = decompressed_bytes[start_index:]
            xml_text = xml_bytes.decode("utf-8", errors="ignore").replace("\x00", "")
            return f"<Root>{xml_text}</Root>"

    def loadTextures(dcx_path, layout_path):
        """Load textures from the TPF.DCX and parse layout XML."""
        layout_xml = Functions.getLayoutData(layout_path)
        root = ET.fromstring(layout_xml)

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

            # Convert DDS → PIL Image
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
    progress = pyqtSignal(int, str)   # percent, message
    finished = pyqtSignal(dict, dict)  # atlases, subtextures

    def __init__(self, dcx_path, layout_path):
        super().__init__()
        self.dcx_path = dcx_path
        self.layout_path = layout_path

    def run(self):
        try:
            layout_xml = Functions.getLayoutData(self.layout_path)
            root = ET.fromstring(layout_xml)

            self.progress.emit(0, "Opening DCX file...")
            tpfdcx = tpf.TPF.from_path(self.dcx_path)
            self.progress.emit(10, "Parsing textures...")
            textures_dict = {texture.stem: texture for texture in tpfdcx.textures}
            self.progress.emit(20, "Parsing layout XML...")

            atlases = {}
            subtextures = {}

            atlas_nodes = root.findall("TextureAtlas")
            total = len(atlas_nodes)

            for i, texture_atlas in enumerate(atlas_nodes, 1):
                filepath = texture_atlas.get("imagePath")
                filename = Path(filepath).stem

                if filename not in textures_dict:
                    self.progress.emit(int(i/total*100), f"{filename} not found, skipping.")
                    continue

                atlases[filename] = textures_dict[filename]  # store raw texture
                subtextures[filename] = []

                for sub in texture_atlas.findall("SubTexture"):
                    subtextures[filename].append({
                        "name": sub.get("name"),
                        "x": int(sub.get("x")),
                        "y": int(sub.get("y")),
                        "width": int(sub.get("width")),
                        "height": int(sub.get("height")),
                    })

                self.progress.emit(20 + int(i / total * 80), f"Loaded {filename}")

            self.finished.emit(atlases, subtextures)

        except Exception as e:
            self.progress.emit(0, f"Error: {e}")
            self.finished.emit({}, {})

class ExtractWorker(QObject):
    progress = pyqtSignal(int, str) # percent, message
    finished = pyqtSignal()

    def __init__(self, atlases, subtextures, output_dir, loader, tasks=None,):
        super().__init__()
        self.atlases = atlases
        self.subtextures = subtextures
        self.output_dir = output_dir
        self.pilLoader = loader
        self.tasks = tasks if tasks is not None else []
        self._interrupted = False

    def interrupt(self):
        self._interrupted = True

    def run(self):
        import os
        os.makedirs(self.output_dir, exist_ok=True)

        if not self.tasks:
            for atlas_name, atlas_img in self.atlases.items():
                for st in self.subtextures.get(atlas_name, []):
                    self.tasks.append((atlas_name, st))

        total = len(self.tasks)
        for i, (atlas_name, st) in enumerate(self.tasks, 1):

            if self._interrupted:
                break

            atlas_img = self.pilLoader(atlas_name=atlas_name)
            cropped = atlas_img.crop(
                (st["x"], st["y"], st["x"] + st["width"], st["y"] + st["height"])
            )

            out_path = self.output_dir / atlas_name
            os.makedirs(out_path, exist_ok=True)
            cropped.save(out_path / st["name"])

            percent = int(i / total * 100)
            self.progress.emit(percent, f"Exported {st['name']} from {atlas_name}")

        self.finished.emit()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NERSIE")
        self.setGeometry(100, 100, 1100, 700)
        self.createMenu()

        self.current_crop = None
        self.current_atlas = None
        self.thumbnail_cache = {}

        # --- Layout ---
        container = QWidget()
        layout = QHBoxLayout(container)

        splitter = QSplitter(Qt.Horizontal)

        # Left: atlas list
        self.atlas_list = QListWidget()
        
        self.atlas_list.currentItemChanged.connect(self.showAtlas)
        splitter.addWidget(self.atlas_list)

        # Middle: subtexture list
        self.subtexture_list = QListWidget()
        self.subtexture_list.currentItemChanged.connect(self.showSubtexture)
        splitter.addWidget(self.subtexture_list)

        # Right: preview + buttons
        # Right: preview + info + buttons
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # Preview area
        self.preview_label = QLabel("Texture Preview")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("border: 1px solid gray; background: #222; color: white;")
        self.preview_label.setFixedSize(600, 400)  # smaller preview box
        right_layout.addWidget(self.preview_label, alignment=Qt.AlignCenter)
        
        # Info box
        self.info_label = QLabel("Texture Info")
        self.info_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.info_label.setStyleSheet("background: #333; color: white; padding: 6px; border-radius: 4px;")
        self.info_label.setFixedHeight(150)  # fixed space for info text
        right_layout.addWidget(self.info_label)

        # Buttons (optional if you keep them)
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
        menubar = self.menuBar()

        def createAction(name, func):
            action = QAction(name, self)
            action.triggered.connect(func)
            return action

        file_menu = menubar.addMenu("File")
        file_menu.addAction(createAction("Open", self.openDcxDialog))
        file_menu.addAction(createAction("Clear", self.clear))
        file_menu.addAction(createAction("Dump All Subtextures", self.dumpTextures))
        file_menu.addSeparator()
        file_menu.addAction(createAction("Exit", self.close))

        help_menu = menubar.addMenu("Help")
        help_menu.addAction(createAction("About", self.showAbout))

    def clear(self):
        self.atlas_list.clear()
        self.subtexture_list.clear()
        self.preview_label.setText("Select an atlas or subtexture")
        self.info_label.setText("Image info will appear here")

    def openDcxDialog(self):        
        file_path, _ = QFileDialog.getOpenFileName(self, "Navigate to 01_common(_h).tpf.dcx", "", "DCX Files (*.dcx)")
        layout_path, _ = QFileDialog.getOpenFileName(None, "Navigate to 01_common(_h).sblytbnd.dcx", "", "DCX Files (*.dcx)")
        if not file_path or not layout_path:
            return

        self.progress_dialog = QProgressDialog("Loading DCX...", None, 0, 100, self)
        self.progress_dialog.setWindowTitle("Loading")
        self.progress_dialog.setWindowModality(Qt.ApplicationModal)
        self.progress_dialog.setStyleSheet("""QProgressDialog {padding: 0px;margin: 0px;}""")

        self.progress_dialog.show()

        # --- Keep references in self ---
        self.thread = QThread()
        self.worker = LoadWorker(file_path, layout_path)
        self.worker.moveToThread(self.thread)

        # --- Signals ---
        self.worker.progress.connect(self.updateProgress)
        self.worker.finished.connect(self.load_done)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.started.connect(self.worker.run)
        self.thread.start()

    def loadDone(self, atlases, subtextures):
        self.progress_dialog.close()

        if not atlases:
            QMessageBox.critical(self, "Error", "Failed to load textures.")
            return

        self.atlases = atlases
        self.subtextures = subtextures
        self.atlas_list.clear()
        self.atlas_list.addItems(sorted(atlases.keys()))
        self.subtexture_list.clear()
        self.preview_label.setText("Select an atlas or subtexture")
        self.info_label.setText("Image info will appear here")

    def runExtraction(self, tasks=None):
        output_dir = Path.cwd() / "Output"

        self.progress_dialog = QProgressDialog("Exporting...", "Cancel", 0, 100, self)
        self.progress_dialog.setWindowTitle("Exporting")
        self.progress_dialog.setWindowModality(Qt.ApplicationModal)
        self.progress_dialog.canceled.connect(self.worker.interrupt)
        self.progress_dialog.show()

        # Worker + thread
        self.thread = QThread()
        self.worker = ExtractWorker(self.atlases, self.subtextures, output_dir, loader=self.getPilImage, tasks=tasks)
        self.worker.moveToThread(self.thread)

        # Signals
        self.worker.progress.connect(self.updateProgress)
        self.worker.finished.connect(self.extraction_done)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.started.connect(self.worker.run)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()

    def updateProgress(self, percent, message):
        self.progress_dialog.setValue(percent)
        self.progress_dialog.setLabelText(message)

    def extractionDone(self):
        self.progress_dialog.close()
        QMessageBox.information(self, "Done", "Export finished successfully.")

    def showAbout(self):
        QMessageBox.information(
            self,
            "About",
            "This program uses lazy loading to save your memory from getting fucked\n\n"
            "Larger atlases may take a second or two to load."
        )

    def pil2Qpixmap(self, pil_img, max_size=(600, 400)):
        """Convert PIL image → QPixmap with aspect ratio preserved."""
        data = pil_img.tobytes("raw", "RGBA")
        qimg = QImage(data, pil_img.width, pil_img.height, QImage.Format_RGBA8888)
        pixmap = QPixmap.fromImage(qimg)

        # Scale to fit preview area, keeping aspect ratio
        return pixmap.scaled(
            max_size[0],
            max_size[1],
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
    
    def getPngSize(self, pil_img):
        buf = io.BytesIO()
        pil_img.save(buf, format="PNG")
        return len(buf.getvalue())

    def formatImageInfo(self, name, pil_img, img_type="Atlas"):
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
        self.thumbnail_cache[atlas_name] = img  # optional: cache full image or thumbnail
        return img

    def showAtlas(self, current, _previous):
        if not current:
            return
        atlas_name = current.text()
        self.current_atlas = atlas_name
        self.current_crop = None

        atlas_img = self.getPilImage(atlas_name)

        # Create a thumbnail for preview
        preview_img = atlas_img.copy()
        preview_img.thumbnail((600, 400), Image.Resampling.LANCZOS)
        pixmap = self.pil2Qpixmap(preview_img)
        self.preview_label.setPixmap(pixmap)

        # Info Box
        self.info_label.setText(self.formatImageInfo(atlas_name, atlas_img, "Atlas"))

        # Populate subtexture list
        self.subtexture_list.clear()
        for st in self.subtextures.get(atlas_name, []):
            self.subtexture_list.addItem(st["name"])

    def showSubtexture(self, current, _previous):
        if not current or not self.current_atlas:
            return
        name = current.text()
        st = next(s for s in self.subtextures[self.current_atlas] if s["name"] == name)

        atlas_img = self.getPilImage(self.current_atlas)
        cropped = atlas_img.crop((st["x"], st["y"], st["x"] + st["width"], st["y"] + st["height"]))
        cropped.thumbnail((600, 400), Image.Resampling.LANCZOS)
        pixmap = self.pil2Qpixmap(cropped)

        self.preview_label.setPixmap(pixmap)
        self.current_crop = cropped
        self.info_label.setText(self.formatImageInfo(name, cropped, "Subtexture"))

    def saveSelection(self):
        """Save current subtexture (if selected) or whole atlas (if only atlas selected)."""
        if not self.current_atlas:
            QMessageBox.warning(self, "Warning", "No atlas selected.")
            return

        if self.current_crop is not None and self.subtexture_list.currentItem():
            # Subtexture selected
            st = next(
                s for s in self.subtextures[self.current_atlas]
                if s["name"] == self.subtexture_list.currentItem().text()
            )
            self.runExtraction(tasks=[(self.current_atlas, st)])

        else: # No subtexture selected -> export the full atlas
            out_path = Path.cwd() / "Output" /"_Atlases"
            out_path.mkdir(parents=True, exist_ok=True)
            atlas_img = self.getPilImage(self.current_atlas)
            atlas_img.save(out_path / f"{self.current_atlas}.png")
            QMessageBox.information(self, "Saved", f"Atlas {self.current_atlas} saved to {out_path}")

    def saveAll(self):
        """Export all subtextures from the currently selected atlas only."""
        if not self.current_atlas:
            QMessageBox.warning(self, "Warning", "No atlas selected.")
            return

        tasks = [(self.current_atlas, st) for st in self.subtextures.get(self.current_atlas, [])]
        if not tasks:
            QMessageBox.information(self, "Info", f"No subtextures found for {self.current_atlas}.")
            return

        self.runExtraction(tasks=tasks)

    def dumpTextures(self):
        self.runExtraction()

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
