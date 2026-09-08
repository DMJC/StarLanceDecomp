"""RefPack (EA/Origin-era LZ77) decompressor, ported from Lancer.exe's
DecompressRefPackBlock (0x4cc350). See reversing/reverse_engineered_functions.md
Pass 29/42 for the reverse-engineering writeup. Verified byte-exact against
real gamedata/StarLancer/RESOURCE/*.FNT and cd1/*.SPR files.

Usage: python3 refpack_decompress.py <file.fnt|file.spr>
"""
import struct, sys

def refpack_decompress(data):
    """Faithful port of Lancer.exe's DecompressRefPackBlock (0x4cc350).
    Header: 2 bytes magic (0x10 0xFB), 3 bytes big-endian decompressed size,
    then the opcode stream starts immediately (5-byte total header)."""
    assert data[0] == 0x10 and data[1] == 0xFB, "not RefPack"
    out_size = (data[2]<<16)|(data[3]<<8)|data[4]
    pos = 5
    n = len(data)
    out = bytearray()
    def rb(p):
        return data[p] if p < n else 0
    while len(out) < out_size and pos+4 <= n:
        B0=rb(pos);B1=rb(pos+1);B2=rb(pos+2);B3=rb(pos+3)
        if B0 < 0x80:
            lit=B0&3; length=((B0>>2)&7)+3; dist=(((B0>>5)&3)<<8)+B1+1
            pos+=2
        elif B0 < 0xC0:
            lit=B1>>6; length=(B0&0x3F)+4; dist=((B1&0x3F)<<8)+B2+1
            pos+=3
        elif B0 < 0xE0:
            lit=B0&3; length=((((B0>>2)&0x3F)<<8)|B3)&0x3FF; length+=5
            dist=(((B0&0x10)>>4)<<16)+(B1<<8)+B2+1
            pos+=4
        elif B0 < 0xFC:
            length=(B0&0x1F)*4+4
            pos+=1
            for _ in range(length):
                out.append(rb(pos)); pos+=1
            continue
        else:
            length=B0&3
            pos+=1
            for _ in range(length):
                out.append(rb(pos)); pos+=1
            break
        for _ in range(lit):
            out.append(rb(pos)); pos+=1
        src = len(out)-dist
        for _ in range(length):
            out.append(out[src]); src+=1
    return bytes(out[:out_size])

if __name__ == "__main__":
    path = sys.argv[1]
    with open(path,'rb') as f:
        data = f.read()
    out = refpack_decompress(data)
    print(f"{path}: compressed={len(data)} decompressed={len(out)}")
    # Try FontResource header
    if len(out) >= 0x410:
        u0,u1,lineHeight,u2 = struct.unpack('<IIII', out[:16])
        print(f"  as FontResource: unk0={u0:#x} unk1={u1:#x} lineHeight={lineHeight} unk2={u2:#x}")
        offs = struct.unpack('<256I', out[0x10:0x10+1024])
        nonzero = [o for o in offs if o != 0]
        print(f"  glyphOffset[256]: {len(nonzero)} non-null entries, range {min(nonzero) if nonzero else 0}-{max(nonzero) if nonzero else 0}, decompressed size={len(out)}")
        # sanity: check a few glyph records
        for code in [ord('A'), ord('0'), ord(' ')]:
            o = offs[code]
            if o and o+4 <= len(out):
                w = struct.unpack('<I', out[o:o+4])[0]
                print(f"    char {chr(code)!r} (code {code}): offset={o:#x} width={w}")
