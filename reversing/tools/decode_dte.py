"""Decoder for Star Lancer's `.dte` mission files, per
reversing/reverse_engineered_functions.md's `LoadMissionFile`/
`ReadMissionDirectoryEntry` docs (originally Pass 7, extended Pass 84/85).

`.dte` files are RefPack-compressed (see refpack_decompress.py). Once
decompressed, the file is a flat buffer with a 27-entry directory table
at its very start, one 8-byte entry per table:

    offset 0 (4 bytes): header word
        bits 0-15  = a per-file value that VARIES between missions for
                     the same table slot (Pass 85 correction -- NOT a
                     single stable record-type tag). Its role is
                     PER-TABLE: for entry 3 specifically it's the
                     authoritative populated-record COUNT (confirmed
                     Pass 87 via FUN_0045cbc0's loop bound AND
                     cross-checked against real files); other tables'
                     roles for this field are not yet determined.
        bit 24-27  = 4 flag bits, each sets one global in LoadMissionFile
    offset 4 (4 bytes): absolute offset into the SAME decompressed buffer
                        (LoadMissionFile always passes base=start-of-buffer)

Confirmed (Pass 85) via 4 real mission files (mission1/2/5/30.dte): every
mission decompresses to the exact same total size (850919 bytes) and
every directory entry's resolved offset is byte-identical across
missions -- the format is a fixed-size-per-table template, not a
densely-packed variable-length format. Only the *content* within each
table's region varies per mission.

Entry 0 (Ghidra global `DAT_00525fa8`) is confirmed as the mission's
OBJECT/NAME STRING TABLE: a sequence of null-terminated ASCII strings
naming every ship/trigger/navpoint/group the mission places -- e.g. ship
classes (`us_prowler`, `ussr_sabre1`), named capital ships
(`mammoth (ANS Guliver)`), named trigger instances (`Proximity Trigger`,
`ShipReached Trigger`), patrol routes, navpoints, and speech-cue file
references (`ms_speech\\ms_nam1103.ut`).

Entry 3 (Ghidra global `DAT_0052951c`) is confirmed (Pass 86) as the
mission's OBJECT SPAWN TABLE -- a fixed 512-slot array of 76-byte
(`0x4c`) records, stride independently confirmed via
`GetObjectIndexFromPointer`'s `(ptr - base) / 0x4c` in the game's own
code. Each record:

    +0x00 (i32)     objectID   -- editor-assigned ID, roughly increasing
                                  but with gaps; NOT the array index
    +0x04 (i32)     nameIndex  -- byte offset into entry 0's string table
    +0x08 (3x f32)  position   -- world-space X, Y, Z
    +0x1c (3x f32)  position2  -- byte-identical to +0x08 in every record
                                  observed so far; role of the duplicate
                                  not established
    +0x28 (10x i16) tail       -- partially understood: often includes a
                                  heading-like value (frequently 90), -1
                                  sentinels, and a repeating small-int
                                  pair (possibly squadron/group ID) --
                                  not fully mapped

Real objects are packed at the start of the 512-slot array. The valid
count is entry 3's own directory tag (see above) -- NOT a zero-padding
scan: mission30.dte proves the difference matters, since it has only
23 real records (tag=23) but stale, non-zeroed editor garbage
(truncated/overlapping strings from an earlier, larger save of the
mission) continues for many more slots past that point.

The other 25 tables' internal layouts are NOT decoded by this tool --
only their directory-entry location.

Usage: python3 decode_dte.py <mission.dte> [--strings-only] [--objects]
"""
import struct
import sys
import os
import re

MAGIC_REFPACK = b"\x10\xfb"

LABELS = [
    "DAT_00525fa8 (object/name string table)", "DAT_00525f3c", "DAT_005294f8",
    "DAT_0052951c", "DAT_005267cc", "DAT_005294e0", "DAT_00525f88",
    "DAT_005267c0", "DAT_005267d0", "DAT_005256c8", "DAT_005294d8",
    "PTR_DAT_004ef2fc", "DAT_005294fc", "DAT_00529500", "DAT_00525f18",
    "DAT_005256b8", "DAT_00525fb0", "DAT_005294ec", "DAT_00525fb4",
    "DAT_0052950c", "DAT_00525fa0", "(local 6-byte buf, discarded)",
    "DAT_00525278", "PTR_DAT_004ee7d8", "DAT_00525f9c", "DAT_00525f90",
    "DAT_0052570c",
]


def maybe_decompress(data):
    if data[:2] == MAGIC_REFPACK:
        sys.path.insert(0, os.path.dirname(__file__))
        from refpack_decompress import refpack_decompress
        return refpack_decompress(data)
    return data


def read_directory(out):
    """Returns a list of 27 (typeid, flags, absoff) tuples."""
    entries = []
    for i in range(27):
        hdr, reloff = struct.unpack_from('<II', out, i * 8)
        entries.append((hdr & 0xffff, hdr >> 24, reloff))
    return entries


def extract_strings(out, offset, length=4096):
    chunk = out[offset:offset + length]
    return re.findall(rb'[ -~]{3,}', chunk)


def cstr(buf, off):
    if off < 0 or off >= len(buf):
        return None
    end = buf.find(0, off)
    if end < 0:
        return None
    try:
        return buf[off:end].decode('latin1')
    except Exception:
        return None


OBJECT_STRIDE = 0x4c
OBJECT_CAPACITY = 512


def read_objects(out, nameoff, objoff, count):
    """Yields (index, objectID, name, (x,y,z), tail) for the first `count`
    slots -- `count` is entry 3's own directory-entry tag (Pass 87:
    confirmed authoritative via FUN_0045cbc0's loop bound, NOT a
    zero-padding scan -- stale editor garbage can follow real records
    without being zeroed, e.g. mission30.dte's indices 23+)."""
    for i in range(min(count, OBJECT_CAPACITY)):
        base = objoff + i * OBJECT_STRIDE
        obj_id, name_idx = struct.unpack_from('<ii', out, base)
        x, y, z = struct.unpack_from('<3f', out, base + 8)
        tail = struct.unpack_from('<10h', out, base + 0x28)
        name = cstr(out, nameoff + name_idx) if 0 <= name_idx < len(out) else None
        yield i, obj_id, name, (x, y, z), tail


def main():
    path = sys.argv[1]
    strings_only = '--strings-only' in sys.argv
    objects = '--objects' in sys.argv
    data = open(path, 'rb').read()
    out = maybe_decompress(data)
    print(f"{path}: decompressed {len(out)} bytes")

    entries = read_directory(out)
    if strings_only:
        strs = extract_strings(out, entries[0][2], 8192)
        for s in strs:
            print(' ', s.decode('ascii'))
        return

    if objects:
        nameoff = entries[0][2]
        obj_tag, _, objoff = entries[3]
        print(f"  entry3 tag (= object count, Pass 87): {obj_tag}")
        for i, obj_id, name, pos, tail in read_objects(out, nameoff, objoff, obj_tag):
            print(f"  [{i:3}] id={obj_id:4} name={name!r:32s} "
                  f"pos=({pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f}) tail={tail}")
        return

    for i, (typeid, flags, absoff) in enumerate(entries):
        preview = out[absoff:absoff + 16]
        ascii_preview = ''.join(chr(b) if 32 <= b < 127 else '.' for b in preview)
        print(f"  [{i:2}] {LABELS[i]:42s} tag=0x{typeid:04x} flags=0x{flags:x} "
              f"off=0x{absoff:06x} bytes={preview.hex()} ascii={ascii_preview}")


if __name__ == '__main__':
    main()
