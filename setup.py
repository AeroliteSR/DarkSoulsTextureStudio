from cx_Freeze import setup, Executable
import sys

include_files = [
    ("icon.ico", "icon.ico"),
    ("soulstruct/base/textures/texconv.exe", "soulstruct/base/textures/texconv.exe"),
    ("README.md", "README.md"),
    ("LICENSE", "LICENSE")
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
    name="DSTS",
    version="3.2.1",
    description="Dark Souls Texture Studio",
    options={"build_exe": build_exe_options},
    executables=[Executable("DSTS.py", base=base, icon="icon.ico")],
)