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
PyQt5  
Pillow  

# Usage
You can either open a dcx/tpf file or a directory of them (such as your menu folder)  
The leftmost scrollarea are your atlases, the middle is for subtextures, and the right is the preview.  
Modern games (Sekiro and newer) use a layout system to define where subtextures start and end in the atlas,  
this means that they can be automatically cropped to the correct size when loading.  
Older games (DSR and DS3) instead just use a numbered grid system. I have already mapped some of the more uniform atlases in `GameInfo.py`
which will be split correctly into subtextures.  
Dark Souls 2 doesn't use atlases and just keeps a folder of thousands of images, making it hard to organize.  

Note: The high resolution versions of Elden Ring's icons are stored in 00_solo.tpfbdt which you can unpack with WitchyBND.
Be aware that opening this directory in DSIE will use a LOT of resources (over 3GB of RAM in my testing) and will increase by ~4mb for each icon you load.

# Licensing and info:
This project includes code from the SoulStruct library:  
SoulStruct: https://github.com/Grimrukh/soulstruct  
License: [GPL-3.0](https://www.gnu.org/licenses/gpl-3.0.en.html)  
Reference: [SoulStruct Licensing Statement](https://github.com/Grimrukh/soulstruct/blob/main/pyproject.toml#L6)  

Only a small subset of SoulStruct's source code is included in this project. These source files are heavily modified. Please refer to the original source.     
These files remain under the original GPL-3 license.  

This project is also licensed under [GPL-3.0](https://www.gnu.org/licenses/gpl-3.0.en.html),
and any portions that derive from SoulStruct must comply with GPL-3 when redistributed.  
