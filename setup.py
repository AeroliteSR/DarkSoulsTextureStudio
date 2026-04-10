from cx_Freeze import setup, Executable
import sys

include_files = [
    ("icon.ico", "icon.ico"),
    ("soulstruct/base/textures/texconv.exe", "soulstruct/base/textures/texconv.exe")
]

packages = ["soulstruct"]

build_exe_options = {
    "packages": packages,
    "include_files": include_files,
    "include_msvcr": True,
}

base = None
if sys.platform == "win32":
    base = "GUI"

setup(
    name="DSIE",
    version="3.1.2",
    description="Dark Souls Icon Extractor",
    options={"build_exe": build_exe_options},
    executables=[Executable("DSIE.py", base=base, icon="icon.ico")],
)