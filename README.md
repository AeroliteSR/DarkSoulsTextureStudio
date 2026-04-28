# DSTS: Dark Souls Texture Studio
A simple GUI application for managing icons and UI textures in FromSoftware games.  
## Supports:
| Game       | Preview | Export | Replace | Add |
|------------|---------|--------|---------|-----|
| DeS        |   ✅    |  ✅    |   ❌    | ❌  |
| DS:R       |   ✅    |  ✅    |   ✅    | ✅  |
| DS2:SOTFS  |   ✅    |  ✅    |   ✅    | ❌  |
| DS3        |   ✅    |  ✅    |   ✅    | ✅  |
| BB         |   ✅    |  ✅    |   ❌    | ❌  |
| SDT        |   ✅    |  ✅    |   ✅    | ✅  |
| ER         |   ✅    |  ✅    |   ✅    | ✅  |
| NR         |   ✅    |  ✅    |   ✅    | ✅  |

# Prerequisites (pip install):
rich  
constrata  
PySide6  
Pillow  

# Usage
Install either [UXM](https://github.com/Nordgaren/UXM-Selective-Unpack) or [NUXE](https://github.com/JKAnderson/Nuxe), then run it and unpack the Menu folder — or the whole game if you want.

After launching DSTS, you can either open a dcx/tpf file or a directory of them (such as your menu folder) from the File menu.
If the game's root folder is found in the path, it will automatically load everything. Otherwise, it will ask that you select a game type and find layout files if needed. Simply select "Cancel" for said prompt, and atlases will be loaded without processing their subtextures.  

The leftmost scrollarea are your atlases, the middle is for subtextures, and the right is the preview.  
Modern games (Sekiro and newer) use a layout system to define where subtextures start and end in the atlas.  
This means that they can be automatically cropped to the correct size when loading.  
Older games (DSR and DS3) instead just use a numbered grid system. I have already mapped some of the more uniform atlases in `GameInfo.py`
which will be split correctly into subtextures.  
Dark Souls 2 doesn't use atlases and just keeps a folder of thousands of images, making it hard to organize.  
  
_**Note**_: The high resolution versions of Elden Ring and Nightreigns's icons are stored in 00_solo(_h/l).tpfbdt which you can unpack with WitchyBND.  
Be aware that opening this directory in DSTS will use a LOT of resources. (~3.4GB of RAM for ER and ~1.3GB for NR)  
  
## Settings:  
`Custom Names` - This setting replaces the internal names with mapped ones in `GameInfo.py`. 
This setting can be especially useful for if you don't know the ID of an item in a big list, allowing you to search by its display name. 
Some data, such as Nightreign garbs and Sekiro bosses, were mapped manually, but most of it was scripted from Smithbox exports.  
`Hide Blank Icons` - Only for older games with no layout system. DSTS crops the atlases in a grid layout. Because of this, some 'tiles' 
may be blank. DSTS automatically recognises these blank spaces and ignores them when building the subtexture list. Disable this setting to show 
the aforementioned blank spaces, for example, if you wanted to place a new icon in that spot.  
`Calculate Image Size` - When enabled, simulates the creation of a PNG image to display its file size. This info may be nice to know, but it comes at 
a significant performance drop. It is, therefore, disabled by default.  
`Show Icon Borders` - Draws a red bounding box around subtextures wherever possible. This will not be visible on texture dumps or replacements, 
but can be optionally selected for atlas exports.  
`Alpha Threshold` - Any pixel with an alpha value less than or equal to this number will have their RGB values set to 0. Click to update the value.  
  
## Searching entries
You can press the `Search` button on the menu bar to open a prompt for a string. It defaults to Qt.MatchContains within the subtextures list.
If you want it to search through atlases (for example, for DS2), check `Search Atlases`  
  
## Texture replacement
The `Replace` button selects whichever texture you currently have in the preview, whether that is an atlas or one of its subtextures. It then prompts you 
for an image file. The image you selected is then patched into the atlas/icon within memory. Going to `File -> Apply Replacements` will then export your 
changes as a tpf/dcx file, which should work as is. Some testing showed that Witchy seems to find the files to be agreeable.  
  
## Adding custom icons
Pressing `Add` will once again prompt you for an image, this time to append as a completely new entry. After giving your new subtexture a name, 
DSTS will find free space in the atlas to place it, enlarging the image if it doesn't find any. For modern games, the subtexture will 
automatically be added to the layout (.sblytbnd) file as well. For the older games, it will simply attempt to add a new tile, respecting the existing 
grid dimensions. Currently doesn't work on unmapped, non-uniform atlases.  
  
  
# Credits:
A myriad thanks to Kmstr and Managarm for their suggestions, feedback and testing throughout development! :))  
# Licensing and info:
This project includes code from the SoulStruct library:  
SoulStruct: https://github.com/Grimrukh/soulstruct  
License: [GPL-3.0](https://www.gnu.org/licenses/gpl-3.0.en.html)  
Reference: [SoulStruct Licensing Statement](https://github.com/Grimrukh/soulstruct/blob/main/pyproject.toml#L6)  

Only a small subset of SoulStruct's source code is included in this project. These source files are heavily modified. Please refer to the original source.     
These files remain under the original GPL-3 license.  

This project is also licensed under [GPL-3.0](https://www.gnu.org/licenses/gpl-3.0.en.html),
and any portions that derive from SoulStruct must comply with GPL-3 when redistributed.  
