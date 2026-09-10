"""Decoder for Star Lancer's `.dte` mission files, per
reversing/reverse_engineered_functions.md's `LoadMissionFile`/
`ReadMissionDirectoryEntry` docs (originally Pass 7, extended Pass 84/85).

`.dte` files are RefPack-compressed (see refpack_decompress.py). Once
decompressed, the file is a flat buffer with a 27-entry directory table
at its very start, one 8-byte entry per table:

    offset 0 (4 bytes): header word
        bits 0-15  = a per-file value that VARIES between missions for
                     the same table slot (Pass 85 correction -- this is
                     NOT a stable record-type tag as originally assumed;
                     more likely a checksum/version stamp, not resolved)
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
references (`ms_speech\\ms_nam1103.ut`). The other 26 tables' internal
layouts are NOT decoded by this tool -- only their directory-entry
location.

Usage: python3 decode_dte.py <mission.dte> [--strings-only]
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


def main():
    path = sys.argv[1]
    strings_only = '--strings-only' in sys.argv
    data = open(path, 'rb').read()
    out = maybe_decompress(data)
    print(f"{path}: decompressed {len(out)} bytes")

    entries = read_directory(out)
    if strings_only:
        strs = extract_strings(out, entries[0][2], 8192)
        for s in strs:
            print(' ', s.decode('ascii'))
        return

    for i, (typeid, flags, absoff) in enumerate(entries):
        preview = out[absoff:absoff + 16]
        ascii_preview = ''.join(chr(b) if 32 <= b < 127 else '.' for b in preview)
        print(f"  [{i:2}] {LABELS[i]:42s} tag=0x{typeid:04x} flags=0x{flags:x} "
              f"off=0x{absoff:06x} bytes={preview.hex()} ascii={ascii_preview}")


if __name__ == '__main__':
    main()
