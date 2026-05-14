#!/usr/bin/env python3
"""
synth_symvers.py — synthesize a Module.symvers fragment from an OEM
prebuilt .ko, so a source-built consumer can pass modpost when its
producer is OEM-prebuilt-only (the OEM-prebuilt-sibling-producer
class — see WIRE_UP_RECIPE Step 7.8d).

Inputs:
  --from-ko <path>     OEM prebuilt .ko file (the producer)
  --symbol <name>      symbol to extract (repeatable for multi-symbol)
  --src-path <path>    source path written into Module.symvers (synthetic
                       but plausible; modpost only uses this for diagnostic
                       messages, not for resolution)
  --out <path>         Module.symvers fragment output path (truncated +
                       written; existing rows merged via --merge if
                       desired in a future revision)

Output format (matches kernel kbuild Module.symvers exactly):
  0x<8-hex-crc>\\t<symbol>\\t<src-path>\\t<EXPORT_SYMBOL|EXPORT_SYMBOL_GPL>\\t<namespace-or-empty>\\n

Failure modes the tool guards against:
- Symbol not exported by the .ko (no __ksymtab_<sym> entry).
- Symbol's CRC not in __kcrctab (older kernels without
  CONFIG_MODULE_REL_CRCS — not currently supported).
- GPL/non-GPL classification wrong (modpost may accept either at
  link time but mismatched export type can cause runtime
  taint-flag divergence).

The tool DOES NOT verify that the synthetic symvers actually unblocks
modpost — that's the caller's responsibility (run a brunch and confirm
the symbol resolves cleanly).
"""

import argparse
import struct
import sys
from pathlib import Path


def parse_elf64_sections(data):
    """Return {section_name: (offset, size)} from an ELF64 file bytes."""
    if data[:4] != b'\x7fELF' or data[4] != 2:
        raise ValueError("not an ELF64 file")
    # ELF64 header offsets:
    #   e_shoff   @ 0x28 (8 bytes)
    #   e_shentsize @ 0x3a (2 bytes)
    #   e_shnum   @ 0x3c (2 bytes)
    #   e_shstrndx @ 0x3e (2 bytes)
    e_shoff = struct.unpack('<Q', data[0x28:0x30])[0]
    e_shentsize = struct.unpack('<H', data[0x3a:0x3c])[0]
    e_shnum = struct.unpack('<H', data[0x3c:0x3e])[0]
    e_shstrndx = struct.unpack('<H', data[0x3e:0x40])[0]

    # Section header layout (ELF64 Shdr): name(4) type(4) flags(8)
    # addr(8) offset(8) size(8) link(4) info(4) addralign(8) entsize(8)
    def shdr(idx):
        base = e_shoff + idx * e_shentsize
        return struct.unpack('<IIQQQQIIQQ', data[base:base + 64])

    shstr_off = shdr(e_shstrndx)[4]

    def name_at(off):
        end = data.index(b'\x00', shstr_off + off)
        return data[shstr_off + off:end].decode()

    sections = {}
    for i in range(e_shnum):
        name_idx, _type, _flags, _addr, off, size, _link, _info, _align, _entsize = shdr(i)
        sections[name_at(name_idx)] = (off, size)
    return sections


def parse_symbols(data, sections):
    """Return list of (name, value, section_idx) for all symbols."""
    if '.symtab' not in sections or '.strtab' not in sections:
        raise ValueError(".symtab or .strtab missing")
    sym_off, sym_size = sections['.symtab']
    str_off, str_size = sections['.strtab']
    str_blob = data[str_off:str_off + str_size]

    # ELF64 Sym: name(4) info(1) other(1) shndx(2) value(8) size(8)
    SYM_SZ = 24
    syms = []
    for i in range(0, sym_size, SYM_SZ):
        name_idx, _info, _other, shndx, value, _ssize = struct.unpack(
            '<IBBHQQ', data[sym_off + i:sym_off + i + SYM_SZ])
        end = str_blob.index(b'\x00', name_idx)
        name = str_blob[name_idx:end].decode()
        syms.append((name, value, shndx))
    return syms


def find_section_index(sections_list, name):
    """Sections is a list (in order) — return 1-based shndx of `name`."""
    for i, (sname, _) in enumerate(sections_list):
        if sname == name:
            return i
    return None


def extract_crc(ko_path, symbol):
    """Return (crc_u32, is_gpl) for `symbol` in `ko_path`.

    Handles regular (`__kcrctab` + `__ksymtab`) AND GPL-only / mixed
    (`__kcrctab_gpl` + `__ksymtab_gpl`) exports. Real-world OEM
    modules often have both sections (mix of EXPORT_SYMBOL and
    EXPORT_SYMBOL_GPL); the `__crc_<sym>` symbol's section index
    tells us which kcrctab variant its offset is into.
    """
    data = Path(ko_path).read_bytes()
    sections = parse_elf64_sections(data)

    has_regular = '__kcrctab' in sections and '__ksymtab' in sections
    has_gpl = '__kcrctab_gpl' in sections and '__ksymtab_gpl' in sections
    if not has_regular and not has_gpl:
        raise ValueError(f"{ko_path} has neither __kcrctab nor "
                         "__kcrctab_gpl section (no exports, or kernel "
                         "without CONFIG_MODULE_REL_CRCS)")

    syms = parse_symbols(data, sections)

    # Build an ordered section-names list so we can resolve symbol shndx
    # to a section name. (parse_elf64_sections returns an unordered dict;
    # we need the index→name mapping.)
    e_shoff = struct.unpack('<Q', data[0x28:0x30])[0]
    e_shentsize = struct.unpack('<H', data[0x3a:0x3c])[0]
    e_shnum = struct.unpack('<H', data[0x3c:0x3e])[0]
    e_shstrndx = struct.unpack('<H', data[0x3e:0x40])[0]
    shstr_off = struct.unpack('<IIQQQQIIQQ',
                              data[e_shoff + e_shstrndx * e_shentsize:
                                   e_shoff + e_shstrndx * e_shentsize + 64])[4]
    section_names_by_idx = []
    for i in range(e_shnum):
        base = e_shoff + i * e_shentsize
        name_idx = struct.unpack('<I', data[base:base + 4])[0]
        end = data.index(b'\x00', shstr_off + name_idx)
        section_names_by_idx.append(data[shstr_off + name_idx:end].decode())

    # Find the __crc_<symbol> symbol — its `value` is the byte offset
    # within whichever __kcrctab variant holds it; its `shndx` tells us
    # which one. (For mixed-export modules, .symtab __crc_* entries can
    # point at EITHER __kcrctab OR __kcrctab_gpl depending on each
    # symbol's EXPORT_SYMBOL[_GPL] choice.)
    crc_sym_name = f'__crc_{symbol}'
    crc_offset_in_section = None
    crc_shndx = None
    for sname, value, shndx in syms:
        if sname == crc_sym_name:
            crc_offset_in_section = value
            crc_shndx = shndx
            break
    if crc_offset_in_section is None:
        raise ValueError(f"{symbol}: no __crc_{symbol} symbol — "
                         f"either {symbol} is not exported by {ko_path}, "
                         "or the kernel was built without MODVERSIONS")

    # Resolve which kcrctab variant the offset is into, by the symbol's
    # section index. Reject if shndx isn't __kcrctab or __kcrctab_gpl
    # (would indicate ELF corruption or unsupported export model).
    if crc_shndx is None or crc_shndx >= len(section_names_by_idx):
        raise ValueError(f"{symbol}: __crc_{symbol} has invalid shndx={crc_shndx}")
    kcrctab_section = section_names_by_idx[crc_shndx]
    if kcrctab_section not in ('__kcrctab', '__kcrctab_gpl'):
        raise ValueError(f"{symbol}: __crc_{symbol} lives in unexpected "
                         f"section '{kcrctab_section}' (shndx={crc_shndx})")
    crctab_off, crctab_size = sections[kcrctab_section]
    if crc_offset_in_section + 4 > crctab_size:
        raise ValueError(f"{symbol}: __crc offset {crc_offset_in_section:#x} "
                         f"exceeds {kcrctab_section} size {crctab_size:#x}")

    crc_u32 = struct.unpack('<I',
                            data[crctab_off + crc_offset_in_section:
                                 crctab_off + crc_offset_in_section + 4])[0]

    # GPL classification: we already resolved kcrctab_section above
    # ('__kcrctab' vs '__kcrctab_gpl'). The kcrctab variant matches the
    # __ksymtab variant in normal builds, so we can infer GPL-ness
    # directly without re-scanning the symbol table.
    is_gpl = (kcrctab_section == '__kcrctab_gpl')

    return crc_u32, is_gpl


def main():
    ap = argparse.ArgumentParser(
        description="Synthesize a Module.symvers fragment from an OEM .ko."
    )
    ap.add_argument('--from-ko', required=True,
                    help="OEM prebuilt .ko (the producer)")
    ap.add_argument('--symbol', action='append', required=True,
                    help="symbol name (repeatable)")
    ap.add_argument('--src-path', required=True,
                    help="synthetic source path for the Module.symvers row "
                         "(use a plausible path, e.g. the OEM .ko's logical "
                         "tree position without the .ko extension)")
    ap.add_argument('--out', required=True,
                    help="output Module.symvers path (truncated)")
    args = ap.parse_args()

    rows = []
    for sym in args.symbol:
        try:
            crc, is_gpl = extract_crc(args.from_ko, sym)
        except ValueError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(2)
        export_type = 'EXPORT_SYMBOL_GPL' if is_gpl else 'EXPORT_SYMBOL'
        # Format: 0x<crc>\t<sym>\t<src>\t<export>\t<namespace>\n
        # Namespace is always empty for our use; trailing tab + newline is
        # the kernel's emitted format (verified against
        # audio-kernel/Module.symvers).
        row = f"0x{crc:08x}\t{sym}\t{args.src_path}\t{export_type}\t\n"
        rows.append(row)
        print(f"  {sym}: CRC=0x{crc:08x} ({'GPL' if is_gpl else 'non-GPL'})",
              file=sys.stderr)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(''.join(rows))
    print(f"Wrote {len(rows)} row(s) to {out_path}", file=sys.stderr)


if __name__ == '__main__':
    main()
