# Changelog

## Unreleased

- `gfxdump.py`: graphics family ABI (IOAcceleratorFamily2, IOGraphicsFamily, IOSurface) from both kernel collections, in `dump.py`'s layout. Baselines in `abi/graphics/` for 20G1443, 21H1320, 22H730, 23J631, 24H32 and 25G241 (2026-10-21).

## 0.1.0 (2026-10-19)

- First release as its own repo. The tools were written for the MT7925 native Wi-Fi driver and lived in its `tools/kcabi`.
- `linkcheck.py`, `kcfile.py`, `disasm.py`, `dump.py`, `compare.py`, `genhdr.py`, `refresh.py`, `functions-extra.txt`.
- Default paths can be changed: `KCABI_KC`, `KCABI_CACHE`, `KCABI_REF`, `KCABI_DUMPS`, `KCABI_ROOT`, `LLVM_OBJDUMP`. `dump.py` writes to `./dumps/<build>` by default and runs without a reference dump.
- `refresh.py` no longer builds one particular kext: it prints the verdict, sets its exit status (0, 3, 4) and runs the build command given after `--`.
- `linkcheck.py --help`.
- Tested on macOS 26.7.1 (25G241), x86_64.
