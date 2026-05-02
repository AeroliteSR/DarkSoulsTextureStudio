from __future__ import annotations
# Basic Modules
import os
import numpy as np
from io import BytesIO
from copy import deepcopy
from tempfile import NamedTemporaryFile
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
import traceback
# GUI
from PySide6.QtCore import QObject, Signal
# Soulstruct
from soulstruct.containers.tpf import TPF, TPFPlatform, TPFTexture
from soulstruct.dcx import core
# Custom
from DSTextureStudio.GameInfo import Maps
from DSTextureStudio.Dataclasses import *
from DSTextureStudio.Enums import *
from DSTextureStudio.Helpers import *


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
        if self.game.type == GameType.MODERN: # sblyt is used
            self.processModern()
        else: # DS/PS
            self.processOld()

    def handleUnpack(self, path):
        if self.game.type == GameType.PS:
            try:
                tex,_ = core.decompress(path)
                tpfdcx = TPF.from_bytes(tex)
            except core.DCXError:
                tpfdcx = TPF(path) # it's probably a tpf file, may as well try
        else:
            tpfdcx = TPF(path)

        self.LOADED_DCX_FILES[path.name] = tpfdcx

        for texture in tpfdcx.textures:
            if self.game.type == GameType.PS:
                if self.game.name == "Bloodborne":
                    platform = TPFPlatform.PS4
                elif self.game.name == "Demon's Souls":
                    platform = TPFPlatform.PC

                dds_data = texture.get_headerized_data(platform)

                texture = TPFTexture(    
                    stem=texture.stem,
                    data=dds_data,
                    platform=platform,
                    console_info=texture.console_info,
                    format=texture.format,
                    texture_type=texture.texture_type,
                    mipmap_count=texture.mipmap_count,
                    texture_flags=texture.texture_flags)
            
            yield texture

    def generateTextDict(self, dcx_path, percent):
        textures_dict: dict = {}
        self.progress.emit(percent, f"Unpacking {dcx_path.stem}...")

        paths = []
        if dcx_path.is_dir():
            paths = [Path(dcx_path) / f for f in os.listdir(dcx_path) if f.endswith('tpf.dcx') or f.endswith('.tpf')]
        else:
            paths = [Path(dcx_path)]

        for path in paths:
            for texture in self.handleUnpack(path):
                textures_dict[texture.stem] = texture

        self.progress.emit(percent, f"Loaded {dcx_path.stem}")
        return textures_dict

    def processModern(self):
        try:
            atlases: dict[str, Atlas] = {}
            subtextures: dict[str, dict[str, SubTexture]] = {}
            total_files = len(self.file_mappings)

            self.progress.emit(0, f'Loading {total_files} files...')
            for f_idx, file in enumerate(self.file_mappings, 1):
                percent = int(f_idx / total_files * 100 - 1)
                if isinstance(file, dict):
                    layout_path = file['layout']
                    textures_dict: dict = self.generateTextDict(file['file'], percent)

                    layout_xml = getLayoutData(layout_path)
                    root = ET.fromstring(layout_xml, parser=ET.XMLParser(encoding="utf-8"))
                    self.progress.emit(percent, "Parsing layout XML...")

                    atlas_nodes = [AtlasLayout.from_element(el) for el in root.findall("TextureAtlas")]
                    self.LAYOUT_FILES[file['file'].name] = atlas_nodes
                    total_atlases = len(atlas_nodes)

                    if total_atlases == 0:
                        self.progress.emit(100, "No atlases found")
                        self.finished.emit({}, {}, {}, {})
                        return

                    for texture_atlas in atlas_nodes:
                        filepath = texture_atlas.image_path
                        filename = Path(filepath).stem

                        if filename not in textures_dict:
                            self.progress.emit(int(f_idx / total_files * 100), f"{filename} not found, skipping.")
                            continue

                        atlases[filename] = Atlas(name=filename, texture=textures_dict[filename], parent=file['file'])
                        subtextures[filename] = {}

                        for sub in texture_atlas.iter_subtextures():
                            name = Path(sub.get("name")).stem

                            subtextures[filename][name] = SubTexture(name=name,
                                                                     x=int(sub.get("x")),
                                                                     y=int(sub.get("y")),
                                                                     width=int(sub.get("width")),
                                                                     height=int(sub.get("height")),
                                                                     blank=False)

                elif isinstance(file, Path):
                    textures_dict: dict = self.generateTextDict(file, percent)
                    # add any textures that were not included in the layout
                    for name, texture in textures_dict.items():
                        if name not in atlases:
                            atlases[name] = Atlas(name=name, texture=texture, parent=file)
                            subtextures[name] = {}  # no layout info since single textures go to atlases

            self.finished.emit(atlases, subtextures, self.LOADED_DCX_FILES, self.LAYOUT_FILES)
            self.progress.emit(100, 'Successfully loaded all files!')

        except Exception as e:
            print(e)
            self.progress.emit(0, f"Error: {e}")
            self.finished.emit({}, {}, {}, {})

    def processOld(self):  
        try:
            atlases: dict[str, Atlas]
            subtextures: dict[str, dict[str, SubTexture]]
            total_files = len(self.file_mappings)

            for f_idx, file in enumerate(self.file_mappings, 1):
                percent = int(f_idx / total_files * 100 - 1)
                textures_dict: dict = self.generateTextDict(file, percent)

                for name, texture in textures_dict.items():
                    atlases[name] = Atlas(name=name, texture=texture, parent=file)
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

                            subtextures[name][str(idx)] = SubTexture(name=name,
                                                                     x=x,
                                                                     y=y,
                                                                     width=tile_width,
                                                                     height=tile_height,
                                                                     blank=isBlank)
                            
                        self.progress.emit(percent, f"Processed {name}")

            self.finished.emit(atlases, subtextures, self.LOADED_DCX_FILES, {})

        except Exception as e:
            traceback.print_exc()
            self.progress.emit(0, f"Error: {e}")
            self.finished.emit({}, {}, {}, {})

class ExtractWorker(QObject):
    progress = Signal(int, str) # percent, message
    finished = Signal(bool) # success

    def __init__(self, atlases, subtextures, output_dir, loader, tasks=None, mode=ExportMode.SUBTEXTURE, filetype='png', gridOverlay=False):
        super().__init__()
        self.atlases = atlases
        self.subtextures = subtextures
        self.output_dir = output_dir
        self.pilLoader = loader
        self.tasks = tasks if tasks is not None else []
        self.mode = mode
        self.filetype = filetype
        self.gridOverlay = gridOverlay
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
                texture: TPFTexture = self.atlases[atlas_name]['texture']
                texture.write_dds(Path(self.output_dir) / ".Atlases" / f"{atlas_name}.dds")
                self.progress.emit(100, f"Exported atlas: {atlas_name}")

            else:
                atlas_img = self.pilLoader(atlas_name=atlas_name)
                percent = int(i / total * 100 - 1)

                if self.mode == ExportMode.ATLAS:
                    out_path = self.output_dir / '.Atlases'
                    filename = atlas_name
                    message = f"Exported atlas: {atlas_name}"

                    if self.gridOverlay:
                        atlas_img = createDebugGrid(atlas_img, self.subtextures[atlas_name])

                elif self.mode == ExportMode.SUBTEXTURE:
                    out_path = self.output_dir / atlas_name
                    filename = st
                    message = f"Exported {st} from {atlas_name}"
                    st: SubTexture = self.subtextures[atlas_name][st]
                    atlas_img = atlas_img.crop(st.box()) # crop if in subtexture mode

                self.exportImg(image=atlas_img, filename=filename, out_path=out_path, progress=percent, message=message)

        self.finished.emit(True)

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
                lyt_name = replaceTerms(base_name.split('.')[0], {"_h": "", "_l": ""}) if self.game.name == 'Nightreign' else ""
                processLayout({dcx_path: add_data}, self.output_dir, self.game, lyt_name, format_mode=self.RESOLUTIONS.get(lyt_name, "H"))

            additions_by_atlas = {}
            for sub in add_data["additions"]:
                if sub.parent is None:
                    continue
                atlas_name = sub.parent
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
                add_names = [sub.name for sub in ops['additions']]
                print(f"  Atlas: {atlas_name} | Replacements: {rep_keys if rep_keys != [None] else ['*Self*']} | Additions: {add_names}")

        return dcx_ops

    def run(self):
        try:
            for base_name, atlases in self.buildOperations().items():
                base: TPF = deepcopy(self.LOADED_DCX_FILES[base_name])
                atlas_cache = {}

                for atlas_name, ops in atlases.items():
                    if atlas_name not in atlas_cache:
                        atlas_cache[atlas_name] = self.getPilImage(atlas_name).copy()
                    atlas_img = atlas_cache[atlas_name]

                    for add in ops["additions"]:
                        add.paste_into(atlas_img)
                        #atlas_img.paste(add.img, (add.x, add.y))

                    for sub_name, new_img in ops["replacements"].items():
                        if sub_name:  # subtexture replacement
                            st = self.subtextures.get(atlas_name, {}).get(sub_name)
                            if not st:
                                raise Exception(f"Could not resolve subtexture '{sub_name}' in atlas '{atlas_name}'")
                            #atlas_img.paste(new_img, (st.x, st.y))
                            st.paste_into(atlas_img)
                        else:  # full atlas replacement
                            atlas_img = new_img.copy()
                            atlas_cache[atlas_name] = atlas_img

                for atlas_name, atlas_img in atlas_cache.items():
                    with NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                        temp_path = tmp.name
                        atlas_img.save(temp_path)
                    try:
                        texture = TPF.find_texture_stem(base, atlas_name)
                        texture.replace_dds(temp_path)
                    finally:
                        if os.path.exists(temp_path):
                            os.remove(temp_path)

                base.write(self.output_dir / base_name)

            self.finished.emit(True, "All changes applied successfully!")

        except Exception:
            self.finished.emit(False, traceback.format_exc())
