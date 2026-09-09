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
  Decodes every shape in the file to a PNG. If shape 0 is exactly
  768 bytes (256 * 3) and doesn't parse as a plausible ShapeRecord, it's
  treated as an embedded 6-bit-VGA-precision {R,G,B} palette (index 0
  = transparent by convention) and used for every other shape unless
  --palette overrides which shape index to use as the source palette.
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
    os.makedirs(outdir, exist_ok=True)
    data = open(path, 'rb').read()
    out = maybe_decompress(data)

    unk0, shapeCount = struct.unpack_from('<II', out, 0)
    shapes = []
    for i in range(shapeCount):
        recOff, palOff = struct.unpack_from('<II', out, 8 + i * 8)
        shapes.append((recOff, palOff))

    # find an embedded whole-file palette: a shape entry that does NOT
    # parse as a plausible ShapeRecord, sitting in a 768-byte gap before
    # the next real shape.
    palette = None
    palette_shape_idx = None
    for i, (recOff, palOff) in enumerate(shapes):
        if not looks_like_shape_record(out, recOff):
            # does it span exactly 768 bytes to the next shape (or EOF)?
            nxt = shapes[i + 1][0] if i + 1 < len(shapes) else len(out)
            if nxt - recOff == 768:
                palette = load_palette(out, recOff)
                palette_shape_idx = i
                break

    if palette is None:
        # fallback: greyscale ramp so output is still viewable
        palette = [(i, i, i) for i in range(256)]

    print(f"{path}: shapeCount={shapeCount}, palette from shape {palette_shape_idx}")

    from PIL import Image
    for i, (recOff, palOff) in enumerate(shapes):
        if i == palette_shape_idx:
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
                r, g, b = palette[idx]
                a = 0 if idx == 0 else 255
                px[xx, yy] = (r, g, b, a)
        base = os.path.splitext(os.path.basename(path))[0]
        img.save(os.path.join(outdir, f"{base}_shape{i}.png"))


if __name__ == '__main__':
    main()
