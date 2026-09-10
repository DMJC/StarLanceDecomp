"""Decoder for WinVFX .SPR (Shape) resources, per
reversing/reverse_engineered_functions.md's ShapeSet/ShapeRecord docs
(Pass 39/41) plus the RLE format newly decoded directly from
VFX_shape_blit_unclipped (WINVFX8.DLL, 0x100035fc) while investigating
the medal-case sprites.

ShapeSet:
    +0x00 version string ("1.40" as 4 raw bytes)
    +0x04 shapeCount (u32)
    +0x08 shapes[shapeCount] = {recordOffset:u32, paletteOffset:u32}

ShapeRecord (at recordOffset):
    +0x00 headerField0 (u32, unresolved)
    +0x04 headerField1/originXY (u32, unresolved)
    +0x08 boundX1, boundY1, boundX2, boundY2 (i32 x4)
    +0x18 RLE pixel data, row-major, one row per scanline (boundY2-boundY1+1 rows)

Per-row RLE opcode stream (newly decoded this pass):
    Read a control byte CB. mode = CB & 1, count = CB >> 1.
    - CB == 0x00                    : end of row.
    - mode==0 (even), count>0       : REPEAT run -- next byte is a fill color,
                                        write `count` copies of it.
    - mode==1 (odd), count>0        : LITERAL run -- next `count` bytes are
                                        copied verbatim.
    - mode==1, count==0 (CB==0x01)  : SKIP run -- next byte is a transparent-
                                        pixel skip distance (cursor advances,
                                        nothing written).

Usage: python3 decode_spr.py <file.spr> <outdir> [--palette N]
  Decodes every shape in the file to a PNG. Any shape entry that is
  exactly 768 bytes (256 * 3) away from the next shape and doesn't parse
  as a plausible ShapeRecord is treated as an embedded 6-bit-VGA-precision
  {R,G,B} palette block (index 0 = transparent by convention). Multiple
  such blocks can appear through one file (confirmed in CAPSHIPS.SPR,
  Pass 78: shapeCount 57 = 19 groups of {1 palette, 2 ships}, each group
  with its own dedicated palette so its 2 ships share a consistent
  faction/national color scheme) -- each real shape uses whichever
  palette block most recently preceded it, not always shape 0.
  --palette forces every shape to use one specific palette-block shape
  index instead of the nearest-preceding one.
"""
import struct, sys, os

MAGIC_REFPACK = b"\x10\xfb"


def maybe_decompress(data):
    if data[:2] == MAGIC_REFPACK:
        sys.path.insert(0, os.path.dirname(__file__))
        from refpack_decompress import refpack_decompress
        return refpack_decompress(data)
    return data


def looks_like_shape_record(out, off):
    if off + 0x18 > len(out):
        return False
    _, _, x1, y1, x2, y2 = struct.unpack_from('<IIiiii', out, off)
    w, h = x2 - x1 + 1, y2 - y1 + 1
    return 0 < w <= 4096 and 0 < h <= 4096


def decode_row(data, pos, dest, width):
    """Decode one RLE-encoded row into `dest` (bytearray of length width). Returns new pos."""
    x = 0
    n = len(data)
    while pos < n:
        cb = data[pos]; pos += 1
        if cb == 0:
            break
        mode = cb & 1
        count = cb >> 1
        if mode == 0:
            color = data[pos]; pos += 1
            for _ in range(count):
                if x < width:
                    dest[x] = color
                x += 1
        elif count == 0:
            skip = data[pos]; pos += 1
            x += skip
        else:
            for _ in range(count):
                if x < width and pos < n:
                    dest[x] = data[pos]
                pos += 1
                x += 1
    return pos


def decode_shape_pixels(out, recOff):
    h0, h1, x1, y1, x2, y2 = struct.unpack_from('<IIiiii', out, recOff)
    w, h = x2 - x1 + 1, y2 - y1 + 1
    pixels = bytearray(w * h)  # 0 = transparent/background sentinel
    pos = recOff + 0x18
    for row in range(h):
        rowbuf = bytearray(w)
        pos = decode_row(out, pos, rowbuf, w)
        pixels[row * w:(row + 1) * w] = rowbuf
    return w, h, pixels, (h0, h1, x1, y1, x2, y2)


def load_palette(out, palRecOff):
    raw = out[palRecOff:palRecOff + 768]
    pal = []
    for i in range(256):
        r, g, b = raw[i * 3], raw[i * 3 + 1], raw[i * 3 + 2]
        # 6-bit VGA precision -> 8-bit
        pal.append((min(r * 4, 255), min(g * 4, 255), min(b * 4, 255)))
    return pal


def main():
    path = sys.argv[1]
    outdir = sys.argv[2] if len(sys.argv) > 2 else '.'
    force_palette_idx = None
    if '--palette' in sys.argv:
        force_palette_idx = int(sys.argv[sys.argv.index('--palette') + 1])
    os.makedirs(outdir, exist_ok=True)
    data = open(path, 'rb').read()
    out = maybe_decompress(data)

    unk0, shapeCount = struct.unpack_from('<II', out, 0)
    shapes = []
    for i in range(shapeCount):
        recOff, palOff = struct.unpack_from('<II', out, 8 + i * 8)
        shapes.append((recOff, palOff))

    # Find every embedded palette block: a shape entry that does NOT parse
    # as a plausible ShapeRecord, sitting in a 768-byte gap before the next
    # shape. A file can have several (one per group) -- each real shape
    # uses whichever palette block most recently preceded it.
    palette_blocks = {}  # shape index -> palette
    for i, (recOff, palOff) in enumerate(shapes):
        if not looks_like_shape_record(out, recOff):
            nxt = shapes[i + 1][0] if i + 1 < len(shapes) else len(out)
            if nxt - recOff == 768:
                palette_blocks[i] = load_palette(out, recOff)

    grey_fallback = [(i, i, i) for i in range(256)]
    if force_palette_idx is not None:
        default_palette = palette_blocks.get(force_palette_idx, grey_fallback)
    else:
        default_palette = next(iter(palette_blocks.values()), grey_fallback)

    print(f"{path}: shapeCount={shapeCount}, {len(palette_blocks)} palette block(s) at shapes {sorted(palette_blocks)}")

    from PIL import Image
    current_palette = default_palette
    for i, (recOff, palOff) in enumerate(shapes):
        if i in palette_blocks:
            if force_palette_idx is None:
                current_palette = palette_blocks[i]
            print(f"  shape {i}: palette block, now active for subsequent shapes")
            continue
        if not looks_like_shape_record(out, recOff):
            print(f"  shape {i}: does not look like a valid ShapeRecord, skipping")
            continue
        w, h, pixels, hdr = decode_shape_pixels(out, recOff)
        print(f"  shape {i}: {w}x{h} header={hdr}")
        img = Image.new('RGBA', (w, h))
        px = img.load()
        for yy in range(h):
            for xx in range(w):
                idx = pixels[yy * w + xx]
                r, g, b = current_palette[idx]
                a = 0 if idx == 0 else 255
                px[xx, yy] = (r, g, b, a)
        base = os.path.splitext(os.path.basename(path))[0]
        img.save(os.path.join(outdir, f"{base}_shape{i}.png"))


if __name__ == '__main__':
    main()
