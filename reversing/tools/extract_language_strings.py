"""Extract the Win32 RT_STRING resource table from Lancer.exe's LANGUAGE.DLL
(or ITACLANG.DLL, which uses the identical format). Written for Pass 77 to
resolve the actual text behind GetLanguageString() IDs referenced throughout
reverse_engineered_functions.md -- Ghidra has no visibility into this DLL's
resources, so this reads the PE resource directory directly.

Standard Win32 STRINGTABLE layout: each RT_STRING resource "block" (name ID N)
holds 16 consecutive string IDs ((N-1)*16 .. (N-1)*16+15), each stored as a
2-byte UTF-16 character count followed by that many UTF-16LE code units (no
null terminator; a 0 count means that ID is unused).

Usage: python3 extract_language_strings.py <file.dll> [id_or_id-range ...]
  No extra args: prints every resolved string as "<id>: <text>".
  One or more "N" or "N-M" args: prints only those IDs (still only if present).
"""
import struct
import sys


def _read_dir(data, off):
    _, _, _, _, num_named, num_id = struct.unpack_from('<IIHHHH', data, off)
    entries = []
    entry_off = off + 16
    for _ in range(num_named + num_id):
        entry_id, offset_to_data = struct.unpack_from('<II', data, entry_off)
        entries.append((entry_id, offset_to_data))
        entry_off += 8
    return entries


def extract_strings(path):
    data = open(path, 'rb').read()
    e_lfanew = struct.unpack_from('<I', data, 0x3c)[0]
    assert data[e_lfanew:e_lfanew + 4] == b'PE\x00\x00', 'not a PE file'
    coff_off = e_lfanew + 4
    _, nsections = struct.unpack_from('<HH', data, coff_off)
    opt_hdr_size = struct.unpack_from('<H', data, coff_off + 16)[0]
    opt_hdr_off = coff_off + 20
    magic = struct.unpack_from('<H', data, opt_hdr_off)[0]
    data_dir_off = opt_hdr_off + (96 if magic == 0x10b else 112)
    res_rva, _ = struct.unpack_from('<II', data, data_dir_off + 2 * 8)

    sections = []
    sec_off = opt_hdr_off + opt_hdr_size
    for _ in range(nsections):
        vsize, vaddr, rawsize, rawptr = struct.unpack_from('<IIII', data, sec_off + 8)
        sections.append((vaddr, vsize, rawptr, rawsize))
        sec_off += 40

    def rva_to_off(rva):
        for vaddr, vsize, rawptr, rawsize in sections:
            if vaddr <= rva < vaddr + max(vsize, rawsize):
                return rawptr + (rva - vaddr)
        return None

    res_off = rva_to_off(res_rva)
    results = {}
    for type_id, type_off in _read_dir(data, res_off):
        if type_id != 6:  # RT_STRING
            continue
        for name_id, name_off in _read_dir(data, res_off + (type_off & 0x7fffffff)):
            for _lang_id, data_entry_off in _read_dir(data, res_off + (name_off & 0x7fffffff)):
                entry_off = res_off + (data_entry_off & 0x7fffffff)
                data_rva, data_size, _, _ = struct.unpack_from('<IIII', data, entry_off)
                block = data[rva_to_off(data_rva):rva_to_off(data_rva) + data_size]
                base_id = (name_id - 1) * 16
                pos = 0
                for i in range(16):
                    if pos + 2 > len(block):
                        break
                    length = struct.unpack_from('<H', block, pos)[0]
                    pos += 2
                    if length:
                        results[base_id + i] = block[pos:pos + length * 2].decode('utf-16le', errors='replace')
                    pos += length * 2
    return results


def main():
    path = sys.argv[1]
    results = extract_strings(path)
    wanted = None
    if len(sys.argv) > 2:
        wanted = set()
        for arg in sys.argv[2:]:
            if '-' in arg:
                lo, hi = arg.split('-')
                wanted.update(range(int(lo), int(hi) + 1))
            else:
                wanted.add(int(arg))
    for sid in sorted(results):
        if wanted is None or sid in wanted:
            print(f'{sid}: {results[sid]!r}')


if __name__ == '__main__':
    main()
