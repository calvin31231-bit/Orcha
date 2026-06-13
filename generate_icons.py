"""
Generate placeholder Tauri icons for Mordu Market Engine.
Run once before building: python generate_icons.py
"""
import os
import struct
import zlib

ICONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src-tauri", "icons")
os.makedirs(ICONS_DIR, exist_ok=True)


def make_png(size: int, color=(30, 58, 138)) -> bytes:
    width = height = size
    r, g, b = color

    def chunk(name: bytes, data: bytes) -> bytes:
        c = name + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    raw_rows = b"".join(b"\x00" + bytes([r, g, b] * width) for _ in range(height))
    compressed = zlib.compress(raw_rows)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", compressed)
    png += chunk(b"IEND", b"")
    return png


for size in [32, 128]:
    with open(os.path.join(ICONS_DIR, f"{size}x{size}.png"), "wb") as f:
        f.write(make_png(size))
    print(f"  Created: {size}x{size}.png")

with open(os.path.join(ICONS_DIR, "128x128@2x.png"), "wb") as f:
    f.write(make_png(256))
print("  Created: 128x128@2x.png")


def make_dib(size: int, color=(30, 58, 138)) -> bytes:
    """Classic uncompressed BMP/DIB icon entry that Windows RC.EXE accepts.

    RC.EXE rejects PNG-compressed icon entries for standard sizes, so each
    entry is a BITMAPINFOHEADER + 32bpp BGRA pixels (bottom-up) + 1bpp AND mask.
    """
    r, g, b = color
    header = struct.pack(
        "<IiiHHIIiiII",
        40,            # biSize
        size,          # biWidth
        size * 2,      # biHeight (XOR + AND masks)
        1,             # biPlanes
        32,            # biBitCount
        0,             # biCompression = BI_RGB
        0,             # biSizeImage (0 allowed for BI_RGB)
        0, 0, 0, 0,    # ppm + colors (unused)
    )
    pixel = bytes([b, g, r, 255])           # BGRA, fully opaque
    xor = pixel * (size * size)
    row_bytes = ((size + 31) // 32) * 4     # AND mask rows padded to 4 bytes
    and_mask = b"\x00" * (row_bytes * size)
    return header + xor + and_mask


def make_ico() -> bytes:
    sizes = [16, 32, 48]
    dibs = [make_dib(s) for s in sizes]
    header_size = 6
    dir_entry_size = 16
    offset = header_size + dir_entry_size * len(sizes)
    ico = struct.pack("<HHH", 0, 1, len(sizes))
    for s, dib in zip(sizes, dibs):
        ico += struct.pack("<BBBBHHII", s if s < 256 else 0, s if s < 256 else 0, 0, 0, 1, 32, len(dib), offset)
        offset += len(dib)
    for dib in dibs:
        ico += dib
    return ico


with open(os.path.join(ICONS_DIR, "icon.ico"), "wb") as f:
    f.write(make_ico())
print("  Created: icon.ico")

with open(os.path.join(ICONS_DIR, "icon.icns"), "wb") as f:
    f.write(make_png(512))
print("  Created: icon.icns (stub - replace with real .icns for Mac release)")

print("\nIcons generated! For production, replace with branded assets.")
