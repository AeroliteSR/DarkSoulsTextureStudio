"""Console DDS deswizzle methods, adapted from `DrSwizzler` by Shadowth117.

See:
    https://github.com/Shadowth117/DrSwizzler
"""
from __future__ import annotations

__all__ = [
    "DDSDeswizzleError",
    "deswizzle_dds_bytes_ps3",
    "deswizzle_dds_bytes_ps4",
]

from soulstruct.exceptions import SoulstructError
from .enums import *
from .utilities import *


class DDSDeswizzleError(SoulstructError):
    """Base DDS deswizzler error."""


def deswizzle_dds_bytes_ps3(swizzled: bytes, dxgi_format: DXGI_FORMAT, width: int, height: int) -> bytes:
    bits_per_pixel, pixel_block_size, dds_bytes_per_pixel_set = dxgi_format.get_format_info()
    print(f"Deswizzle PS3: {dxgi_format}, {width}, {height}")
    print(f"  bpp: {bits_per_pixel}, block size: {pixel_block_size}, bytes per pixel set: {dds_bytes_per_pixel_set}")
    if dds_bytes_per_pixel_set >= len(swizzled):
        raise DDSDeswizzleError(
            f"DDS texture is too small to contain a single pixel set (expected {dds_bytes_per_pixel_set} bytes)."
        )
    deswizzled_size = max((width * height * bits_per_pixel) // 8, dds_bytes_per_pixel_set)
    deswizzled = bytearray(b"\0" * deswizzled_size)
    sy = height // pixel_block_size
    sx = width // pixel_block_size
    for src_tile_i in range(sx * sy):
        dest_tile_i = morton(src_tile_i, sx, sy)
        swizzled_start = src_tile_i * dds_bytes_per_pixel_set
        swizzled_tile = swizzled[swizzled_start:swizzled_start + dds_bytes_per_pixel_set]
        deswizzled_start = dest_tile_i * dds_bytes_per_pixel_set
        deswizzled[deswizzled_start:deswizzled_start + dds_bytes_per_pixel_set] = swizzled_tile
    return bytes(deswizzled)


"""Rewritten in DSTS, not original to Soulstruct."""
def deswizzle_dds_bytes_ps4(swizzled: bytes, dxgi_format: DXGI_FORMAT, width: int, height: int) -> bytes:
    def morton8(i):
        def compact1by1(n):
            n &= 0x5555
            n = (n ^ (n >> 1)) & 0x3333
            n = (n ^ (n >> 2)) & 0x0F0F
            n = (n ^ (n >> 4)) & 0x00FF
            return n

        x = compact1by1(i)
        y = compact1by1(i >> 1)
        return x, y

    bits_per_pixel, pixel_block_size, block_bytes = dxgi_format.get_format_info()

    if block_bytes >= len(swizzled):
        raise ValueError("Texture too small")

    sx = width // pixel_block_size
    sy = height // pixel_block_size
    out_size = max((width * height * bits_per_pixel) // 8, block_bytes)
    out = bytearray(out_size)
    pos = 0

    for ty in range((sy + 7) // 8):
        for tx in range((sx + 7) // 8):
            for t in range(64):
                x, y = morton8(t)
                dst_x = tx * 8 + x
                dst_y = ty * 8 + y

                if pos + block_bytes > len(swizzled):
                    return bytes(out)

                block = swizzled[pos:pos + block_bytes]
                pos += block_bytes

                if dst_x >= sx or dst_y >= sy:
                    continue

                dst_index = (dst_y * sx + dst_x) * block_bytes
                out[dst_index:dst_index + block_bytes] = block

    return bytes(out)