"""
This module originally used a `DCX` class, but I changed it to static functions to avoid the unnecessary OOP confusion
when loading files, since `DCX(data).pack()` and `DCX(path).data` were the most common use cases anyway.
"""
from __future__ import annotations

__all__ = [
    "DCXType",
    "decompress",
]

import logging
import typing as tp
from enum import Enum
from pathlib import Path
from soulstruct.exceptions import SoulstructError
from soulstruct.utilities.binary import *
from . import oodle

_LOGGER = logging.getLogger(__name__)

class DCXVersionInfo(tp.NamedTuple):
    compression_type: bytes
    version1: int
    version2: int
    version3: int | None  # not constant for `DCX_EDGE`
    compression_level: int | None  # not constant for `DCX_ZSTD`
    version5: int
    version6: int
    version7: int

    def __eq__(self, other: DCXVersionInfo):
        """Fields must be equal unless one or both is `None`."""
        for field_name in self._fields:
            if getattr(self, field_name) is None or getattr(other, field_name) is None:
                continue
            if getattr(self, field_name) != getattr(other, field_name):
                return False
        return True

    def __repr__(self) -> str:
        """Convert `int` fields to hex strings."""
        s = f"DCXVersionInfo("
        for _field in self.__annotations__:
            v = getattr(self, _field)
            if isinstance(v, int):
                s += f"{_field}={hex(v)}, "
            else:
                s += f"{_field}={v}, "
        return s[:-2] + ")"

class DCXType(Enum):
    Unknown = -1  # could not be detected
    Null = 0  # no compression
    Zlib = 1  # not really DCX but supported
    DCP_EDGE = 2  # DCP header, chunked deflate compression. Used in ACE:R TPFs.
    DCP_DFLT = 3  # DCP header, deflate compression. Used in DeS test maps.
    DCX_EDGE = 4  # DCX header, chunked deflate compression. Primarily used in DeS.
    DCX_DFLT_10000_24_9 = 5  # DCX header, deflate compression. Primarily used in DS1 and DS2.
    DCX_DFLT_10000_44_9 = 6  # DCX header, deflate compression. Primarily used in BB and DS3.
    DCX_DFLT_11000_44_8 = 7  # DCX header, deflate compression. Used for the backup regulation in DS3 save files.
    DCX_DFLT_11000_44_9 = 8  # DCX header, deflate compression. Used in Sekiro.
    DCX_DFLT_11000_44_9_15 = 9  # DCX header, deflate compression. Used in old ER regulation.
    DCX_KRAK = 10  # DCX header, Oodle compression. Used in Sekiro and Elden Ring.
    DCX_ZSTD = 11  # ZSTD compression. Used in new ER regulation.

    # Game default aliases.
    DES = DCX_EDGE
    DS1_DS2 = DCX_DFLT_10000_24_9
    BB_DS3 = DCX_DFLT_10000_44_9
    SEKIRO = DCX_DFLT_11000_44_9
    ER = DCX_KRAK
    ER_REGULATION = DCX_ZSTD

    def get_version_info(self) -> DCXVersionInfo:
        return DCX_VERSION_INFO[self]

    def has_dcx_extension(self):
        return self.value >= 2

    def process_path(self, path: Path | str) -> Path | str:
        """Add or remove '.dcx' extension to/from `path` as appropriate.

        Returns `Path` or `str` (depending on input type).
        """
        is_path = isinstance(path, Path)
        path = Path(path)
        new_path = path.with_name(path.name.removesuffix(".dcx"))
        if self.has_dcx_extension():
            new_path = path.with_name(path.name + ".dcx")
        return new_path if is_path else str(new_path)

    @classmethod
    def from_member_name(cls, member_name: str) -> DCXType:
        """Getaround for PyCharm's refusal to understand that `Enum.__getitem__()` returns members, not `type[Enum]`."""
        # noinspection PyTypeChecker
        return cls[member_name]

    @classmethod
    def detect(cls, reader: BinaryReader) -> DCXType:
        """Detect type of DCX. Resets offset when done."""
        with reader.temp_offset():
            magic = reader.peek(4)
            if magic == b"DCP\0":  # rare, only for older games and DeS test maps
                # Possible file pattern for DFLT or EDGE compression.
                dcx_fmt = reader.peek(4, 4)
                if dcx_fmt == b"DCP\0":
                    return cls.DCP_DFLT
                elif dcx_fmt == b"EDGE":
                    return cls.DCP_EDGE
                else:
                    return cls.Unknown

            if magic != b"DCX\0":
                b0, b1 = reader.unpack("BB")
                if b0 == 0x78 and (b1 in {0x01, 0x5E, 0x9C, 0xDA}):
                    return cls.Zlib
                return cls.Unknown  # very unlikely to be DCX at this point

            try:
                header = DCXHeaderStruct.from_bytes(reader)
            except BinaryFieldValueError as ex:
                _LOGGER.error(f"Error while trying to detect `DCXType`: {ex}")
                return cls.Unknown

            header_version_info = header.get_version_info()
            for dcx_type, version_info in DCX_VERSION_INFO.items():
                if version_info is None:
                    continue
                if version_info == header_version_info:
                    return dcx_type

            _LOGGER.error(
                f"Unknown configuration of DCX version fields in DCX header:\n"
                f" {header_version_info}\n"
                "  Maybe tell Grimrukh about this new DCX format..."
            )
            return cls.Unknown

# Captures the field values that actually vary across DCX versions.
DCX_VERSION_INFO = {
    DCXType.DCP_DFLT:               None,
    DCXType.DCX_EDGE:               DCXVersionInfo(b"EDGE", 0x10000, 0x24, None, 9,    0x10000, 0,         0x100100),
    DCXType.DCX_DFLT_10000_24_9:    DCXVersionInfo(b"DFLT", 0x10000, 0x24, 0x2C, 9,    0,       0,         0x010100),
    DCXType.DCX_DFLT_10000_44_9:    DCXVersionInfo(b"DFLT", 0x10000, 0x44, 0x4C, 9,    0,       0,         0x010100),
    DCXType.DCX_DFLT_11000_44_8:    DCXVersionInfo(b"DFLT", 0x11000, 0x44, 0x4C, 8,    0,       0,         0x010100),
    DCXType.DCX_DFLT_11000_44_9:    DCXVersionInfo(b"DFLT", 0x11000, 0x44, 0x4C, 9,    0,       0,         0x010100),
    DCXType.DCX_DFLT_11000_44_9_15: DCXVersionInfo(b"DFLT", 0x11000, 0x44, 0x4C, 9,    0,       0xF000000, 0x010100),
    DCXType.DCX_KRAK:               DCXVersionInfo(b"KRAK", 0x11000, 0x44, 0x4C, 6,    0,       0,         0x010100),
    DCXType.DCX_ZSTD:               DCXVersionInfo(b"ZSTD", 0x11000, 0x44, 0x4C, None, 0,       0,         0x010100),
}

class DCXHeaderStruct(BinaryStruct):
    """Compression header (with variation in the `version` fields) in all FromSoft games after Demon's Souls.

    NOTE: Not asserting the five 'version' fields so that we can guess when a new format is available.
    """
    dcx: bytes = binary_string(4, asserted=b"DCX", init=False)
    version1: int  # [0x10000, 0x11000]
    unk1: int = binary(asserted=0x18, init=False)
    unk2: int = binary(asserted=0x24, init=False)
    version2: int  # [0x24, 0x44]
    version3: int  # [0x2C, 0x4C, `0x50 + chunk_count * 0x10` (DCX_EDGE)]
    dcs: bytes = binary_string(4, asserted=b"DCS", init=False)
    decompressed_size: int
    compressed_size: int
    dcp: bytes = binary_string(4, asserted=b"DCP", init=False)
    compression_type: bytes = binary_string(4, asserted=(b"ZSTD", b"EDGE", b"DFLT", b"KRAK"))
    unk3: int = binary(asserted=0x20, init=False)
    compression_level: byte  # [6, 8, 9, variable (DCX_ZSTD)]
    _compression_level_pad: bytes = binary_pad(3, init=False)
    version5: int  # [0, 0x10000]
    version6: int  # [0, 0xF000000]
    unk5: int = binary(asserted=0, init=False)
    version7: int  # [0x10100, 0x101000]

    DEFAULT_BYTE_ORDER = ByteOrder.BigEndian

    def get_version_info(self) -> DCXVersionInfo:
        """Extract non-constant field values."""
        return DCXVersionInfo(
            compression_type=self.compression_type,
            version1=self.version1,
            version2=self.version2,
            version3=self.version3,
            compression_level=self.compression_level,
            version5=self.version5,
            version6=self.version6,
            version7=self.version7,
        )

def decompress(dcx_source: bytes | BinaryReader | tp.BinaryIO | Path | str) -> tuple[bytes, DCXType]:
    """Decompress the given file path, raw bytes, or buffer/reader.

    Returns a tuple containing the decompressed `bytes` and a `DCXInfo` instance that can be used to compress later
    with the same DCX type/parameters.
    """
    reader = BinaryReader(dcx_source, byte_order=ByteOrder.BigEndian)  # always big-endian
    dcx_type = DCXType.detect(reader)
    header = DCXHeaderStruct.from_bytes(reader, byte_order=ByteOrder.BigEndian)
    reader.unpack_bytes(length=4, asserted=b"DCA")
    reader.unpack_value("i", asserted=8)  # compressed header size
    compressed = reader.read(header.compressed_size)
    decompressed = oodle.decompress(compressed, header.decompressed_size)

    if len(decompressed) != header.decompressed_size:
        raise SoulstructError("Decompressed DCX data size does not match size in header.")
    return decompressed, dcx_type

def is_dcx(reader: BinaryReader) -> bool:
    """Checks if file data starts with DCX (or DCP) magic."""
    return reader["4s", 0] in {b"DCP\0", b"DCX\0"}