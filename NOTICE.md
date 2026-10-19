# Notices and sources

## ga403wm-hackintosh (BSD-3-Clause-Clear)

Copyright (c) 2026 thanhnndev and contributors. https://github.com/thanhnndev/ga403wm-hackintosh. Licence text in `LICENSES/BSD-3-Clause-Clear-ga403wm.txt`.

- `kcfile.py` follows the method documented in `tools/kc.py` and `docs/IO80211-ABI-2.md` (symbols from each fileset entry's `LC_SYMTAB`, vtables read from `__ZTV` symbols, kernel-cache chained pointers, class sizes from MetaClass constructors). It is an independent rewrite; no code was copied.
- `linkcheck.py` follows the idea of `tools/check_kext_links.py`, rewritten on top of `kcfile.py`.
- `genhdr.py` adapts the header generation method and the tables of known return types from `tools/io80211_abi.py`, `gen_io80211_header.py`, `io80211_check.py`, `gen_native_iface.py` and `check_native_slots.py`. Those adapted parts stay under BSD-3-Clause-Clear.
- `disasm.py` writes the same line format as that project's 24H32 dumps so both can be compared, and `functions-extra.txt` lists functions its native Wi-Fi work was debugged against.

## Apple

The tools read Apple's kernel collection on your machine. Nothing from it is shipped here. Dumps and generated headers hold class names, slot order, method names and sizes, no Apple code.
