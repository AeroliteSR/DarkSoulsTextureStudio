from PIL import Image, ImageDraw
import xml.etree.ElementTree as ET
import numpy as np
from io import BytesIO
from pathlib import Path
from PySide6.QtWidgets import QListWidgetItem
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import Qt
import re
from .Enums import ResFormat, Game
from .GUI import gameTypeDialog
from soulstruct.containers import Binder, BinderEntry, BinderVersion, BinderVersion4Info
from soulstruct.dcx import core, DCXType

ROOTS = {
        "Sekiro": Path(r"N:\NTC\data\Menu\ScaleForm\SBLayout\01_Common"),

        "Elden Ring": Path(r"N:\GR\data\Menu\ScaleForm\SBLayout\01_Common"),

        "Nightreign": Path(r"W:\CL\data\Target\INTERROOT_win64\menu\ScaleForm\Tif"),
    }


class NaturalListItem(QListWidgetItem):
    def __init__(self, text):
        super().__init__(text)

    @staticmethod
    def naturalSortKey(text):
        return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', text)]
    
    def __lt__(self, other):
        return NaturalListItem.naturalSortKey(self.text()) < NaturalListItem.naturalSortKey(other.text())

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
            atlas_path = replaceTerms(atlas.image_path, {'.png': '', '.tif': ''})
            atlas_subtextures = [sub for sub in to_add if sub.parent in atlas_path]

            atlas.add_subtextures(atlas_subtextures)

        for atlas in data:
            xml_bytes = ET.tostring(atlas.element, encoding='utf-8', method='xml', )
            layout_path = replaceTerms(atlas.image_path, {'.png': '.layout', '.tif': '.layout'})
            entry = BinderEntry(
                data=xml_bytes,
                entry_id=binder.get_first_new_entry_id_in_range(0, 1000000),
                path=str(root / layout_path),
                flags=0x2)
            
            binder.add_entry(entry=entry)

        binder.write(output_dir / output_name)

def getLayoutData(dcx_path):
    with open(dcx_path, "rb") as f:
        decompressed_bytes, _ = core.decompress(f)
        start_index = decompressed_bytes.find(b"<TextureAtlas")
        xml_bytes = decompressed_bytes[start_index:]
        xml_text = xml_bytes.decode("utf-8", errors="ignore").replace("\x00", "")
        return f"<Root>{xml_text}</Root>"

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

def cleanByAlpha(img: Image.Image, threshold: int = 5) -> Image.Image:
    """Zero RGB values where alpha <= threshold."""
    arr = np.array(img)
    mask = arr[..., 3] <= threshold
    arr[mask, :3] = 0
    return Image.fromarray(arr, "RGBA")

def replaceTerms(text, terms: dict):
    if text:
        for term, replacement in terms.items():
            text = text.replace(term, replacement)
    return text
    
def parseGameType(path) -> Game:
    game_type = None
    parts = Path(path).parts

    def has_sequence(parts, sequence):
        for i in range(len(parts) - len(sequence) + 1):
            if parts[i:i+len(sequence)] == tuple(sequence):
                return True
        return False

    if "PS3_GAME" in parts:
        game_type = 'Demon\'s Souls'
    if has_sequence(parts, ["steamapps", "common", "DARK SOULS REMASTERED"]):
        game_type = 'Dark Souls 1'
    elif has_sequence(parts, ["steamapps", "common", "Dark Souls II Scholar of the First Sin"]):
        game_type = 'Dark Souls 2'
    elif has_sequence(parts, ["steamapps", "common", "DARK SOULS III"]):
        game_type = 'Dark Souls 3'
    elif has_sequence(parts, ["Bloodborne", "CUSA03173", "dvdroot_ps4"]):
        game_type = 'Bloodborne'
    elif has_sequence(parts, ["steamapps", "common", "Sekiro"]):
        game_type = 'Sekiro'
    elif has_sequence(parts, ["steamapps", "common", "ELDEN RING NIGHTREIGN"]):
        game_type = 'Nightreign'
    elif has_sequence(parts, ["steamapps", "common", "ELDEN RING"]):
        game_type = 'Elden Ring'

    return Game(game_type)

def createDebugGrid(image, subtextures):
    """Outputs a png with grid lines for debugging"""
    if len(subtextures) == 0:
        return image
    
    debug = image.copy()
    draw = ImageDraw.Draw(debug)

    for icn in subtextures.values():
        width = icn.width
        height = icn.height
        x = icn.x
        y = icn.y
        draw.rectangle([x, y, x + width, y + height], outline="red", width=1)

    return debug

def pil2Qpixmap(pil_img, max_size=(600, 400)) -> QPixmap:
    """Convert PIL Image to QPixmap without destroying the aspect ratio lol"""
    data = pil_img.tobytes("raw", "RGBA")
    qimg = QImage(data, pil_img.width, pil_img.height, QImage.Format_RGBA8888)
    pixmap = QPixmap.fromImage(qimg)

    return pixmap.scaled(max_size[0], max_size[1], Qt.KeepAspectRatio, Qt.SmoothTransformation)

def getPngSize(pil_img):
    """Simulate a png export to get file size."""
    buf = BytesIO()
    pil_img.save(buf, format="PNG")
    return len(buf.getvalue())

def checkGame(path: str) -> Game:
    game = parseGameType(path=path)
    if game.name is None:
        game = gameTypeDialog()
    return game if game.name is not None else None
