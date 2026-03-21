# DSIE: Dark Souls Icon Extractor
A simple GUI application for previewing and exporting FromSoftware games' icons.  
## Supports:
 - Dark Souls Remastered
 - Dark Souls 2 SOTFS
 - Dark Souls 3
 - Sekiro
 - Elden Ring
 - Nightreign

# Prerequisites (pip install):
rich  
constrata  
PySide6  
Pillow  

# Usage
Install either [UXM](https://github.com/Nordgaren/UXM-Selective-Unpack) or [NUXE](https://github.com/JKAnderson/Nuxe), then run it and unpack the Menu folder — or the whole game if you want.

After launching DSIE, you can either open a dcx/tpf file or a directory of them (such as your menu folder) from the File menu.
If the game's root folder is found in the path, it will automatically load everything. Otherwise, it will ask that you select a game type and find layout files if needed. Simply select "Cancel" for said prompt, and atlases will be loaded without processing their subtextures.  

The leftmost scrollarea are your atlases, the middle is for subtextures, and the right is the preview.  
Modern games (Sekiro and newer) use a layout system to define where subtextures start and end in the atlas.  
This means that they can be automatically cropped to the correct size when loading.  
Older games (DSR and DS3) instead just use a numbered grid system. I have already mapped some of the more uniform atlases in `GameInfo.py`
which will be split correctly into subtextures.  
Dark Souls 2 doesn't use atlases and just keeps a folder of thousands of images, making it hard to organize.  
  
Currently the `Settings` tab has only one option, `Use Names`. This setting replaces the internal names with mapped ones in `GameInfo.py`. 
This setting can be especially useful for if you don't know the ID of an item in a big list, allowing you to search by its display name.  
Some data, such as Nightreign garbs and Sekiro bosses, were mapped manually, but most of it was scripted from Smithbox exports.  

You can press the `Search` button on the menu bar to open a prompt for a string. It defaults to Qt.MatchContains within the subtextures list.
If you want it to search through atlases (for example, for DS2), check `Search Atlases`  
  
The `Replace` button selects whichever texture you currently have in the preview, whether that is an atlas or one of its subtextures. It then prompts you 
for an image file. The image you selected is then patched into the atlas/icon within memory. Going to `File -> Apply Replacements` will then export your 
changes as a tpf/dcx file, which should work as is. Some testing showed that Witchy seems to find the files to be agreeable.  
  
Note: The high resolution versions of Elden Ring and Nightreigns's icons are stored in 00_solo(_h/l).tpfbdt which you can unpack with WitchyBND.  
Be aware that opening this directory in DSIE will use a LOT of resources (~3.4GB of RAM for ER and ~1.3GB for NR) and will increase by ~4mb for each icon you load.

# Licensing and info:
This project includes code from the SoulStruct library:  
SoulStruct: https://github.com/Grimrukh/soulstruct  
License: [GPL-3.0](https://www.gnu.org/licenses/gpl-3.0.en.html)  
Reference: [SoulStruct Licensing Statement](https://github.com/Grimrukh/soulstruct/blob/main/pyproject.toml#L6)  

Only a small subset of SoulStruct's source code is included in this project. These source files are heavily modified. Please refer to the original source.     
These files remain under the original GPL-3 license.  

This project is also licensed under [GPL-3.0](https://www.gnu.org/licenses/gpl-3.0.en.html),
and any portions that derive from SoulStruct must comply with GPL-3 when redistributed.  
