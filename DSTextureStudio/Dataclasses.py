from dataclasses import dataclass
from typing import Optional
from PIL import Image
from pathlib import Path
from soulstruct.containers.tpf import TPFTexture
import xml.etree.ElementTree as ET

@dataclass(slots=True)
class AtlasLayout:
    element: ET.Element

    @property
    def name(self) -> str:
        return Path(self.image_path).stem
    
    @property
    def image_path(self) -> str:
        return self.element.get("imagePath")
    
    @classmethod
    def from_element(cls, el: ET.Element) -> "AtlasLayout":
        return cls(element=el)

    def iter_subtextures(self):
        return self.element.findall("SubTexture")

    def has_subtexture(self, name: str) -> bool:
        return any(st.get("name") == name for st in self.iter_subtextures())

    def add_subtextures(self, subtextures: list[dict[str, SubTexture]]):
        atlas = self.element
        for sub in subtextures:
            name = sub.name
            if not name.endswith('.png'):
                name = f"{name}.png"

            if self.has_subtexture(name):
                print(f"Subtexture entry `{name}` already exists in layout file. Skipping.")
                continue

            item = ET.SubElement(atlas, "SubTexture", {
                "name": name,
                "x": str(sub.x),
                "y": str(sub.y),
                "width": str(sub.width),
                "height": str(sub.height),
                "half": str(int(sub.half))})
            
            print(f"Adding Subtexture to {sub.parent}:\n{ET.tostring(item, encoding='unicode')}")
            
            if len(atlas) == 1:
                atlas.text = '\r\n\t'
            else:
                atlas[-2].tail = '\r\n\t'

            item.tail = '\r\n'

@dataclass(slots=True)
class Atlas:
    name: str
    texture: TPFTexture
    parent: Path

@dataclass(slots=True)
class SubTexture:
    name: str
    x: int
    y: int
    width: int
    height: int

    img: Optional[Image.Image] = None

    parent: Optional[str] = None
    blank: bool = False
    half: Optional[bool] = False

    def pos(self):
        return (self.x, self.y)

    def box(self, padding: int = 0) -> tuple[int, int, int, int]:
        """Return tuple of coordinates for a box to crop to this subtexture. Allows optional padding"""
        return (self.x - padding, self.y - padding, self.x + self.width + padding, self.y + self.height + padding)
    
    def paste_into(self, atlas_img: Image.Image, mask: Image.Image | None = None) -> None:
        """Pastes self into an image"""
        if self.img is None:
            raise Exception("SubTexture object does not contain an image.")
        atlas_img.paste(self.img, self.box(), mask=mask)