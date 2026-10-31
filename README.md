# WTLKcAbi

Renamed from `kcabi` on 2026-10-31; the command is still `kcabi`. Old links redirect here.

Read-only Python tools for the x86_64 kernel collections of macOS 11 and later (`BootKernelExtensions.kc`, a Mach-O `MH_FILESET`). They answer the questions you hit when you write a kext for a Hackintosh against private Apple classes: will this kext link, what are the vtable slots and instance sizes of an Apple class on this build, and what changed in them after a macOS update.

Nothing here writes to the system. The collection is opened read-only with `mmap`; the only files written are the outputs you name and a cache of carved Mach-O copies.

## The tools

| File | What it does |
|---|---|
| `linkcheck.py` | Checks a built kext's undefined symbols against the collection: each one must be exported by the kernel or by a bundle the kext lists in `OSBundleLibraries`. |
| `kcfile.py` | The reader the others are built on: fileset entries, symbols, vtables, chained pointers, MetaClass instance sizes, carving one entry out for `llvm-objdump`. |
| `disasm.py` | Intel-syntax disassembly of one function through `llvm-objdump`, with symbol names and C strings added as notes, plus a normaliser so two builds can be diffed. |
| `dump.py` | Writes the ABI facts of IO80211Family, IOSkywalkFamily, corecapture and the Broadcom Wi-Fi kexts for one build: vtables, method lists, instance sizes, the apple80211 GET/SET request tables, the WCL event subscriber tables and the disassembly of a list of functions. |
| `compare.py` | Diffs two dumps: size changes, vtable slots that moved, request IDs whose handler changed, and which functions changed (with the field offsets, virtual-call slots and callees that differ). |
| `genhdr.py` | Turns a dump into slot-exact C++ headers for the private IO80211 / IOSkywalk classes a native Wi-Fi driver subclasses, and checks them by compiling a probe subclass with clang and comparing its vtable layout slot by slot with Apple's. |
| `refresh.py` | The after-update command: dump the new build, compare it with the build your kext was verified on, print a verdict (unchanged, relayout, review), optionally run your build script. |
| `gfxdump.py` | The graphics-side ABI of one build (IOAcceleratorFamily2, IOGraphicsFamily, IOSurface): vtables, method lists and instance sizes from both kernel collections, in `dump.py`'s layout so `compare.py` diffs builds. Baselines in `abi/graphics/<build>`. |
| `functions-extra.txt` | Extra functions `dump.py` disassembles on every build (mangled names, a trailing `*` is a prefix). |

`linkcheck.py`, `kcfile.py` and `disasm.py` are general. `dump.py`, `compare.py`, `genhdr.py` and `refresh.py` were written for a native IO80211 front end (the MT7925 driver in [WTLWifiMenu](https://github.com/watchthelight-labs/WTLWifiMenu)); their class lists are at the top of each file and are easy to change for other families.

## Examples

### Will my kext link?

```
python3 linkcheck.py out/MyDriver.kext
python3 linkcheck.py out/MyPlugin.kext --own-lib as.vit9696.Lilu
```

Output for a Lilu plugin on macOS 26.7.1:

```
LegionCpuPower.kext: 327 undefined symbols, collection BootKernelExtensions.kc
  com.apple.iokit.IOACPIFamily                    1  ok
  com.apple.iokit.IOPCIFamily                     2  ok
  com.apple.kernel                              316  ok
  not exported by the collection (8):
    __ZN13KernelPatcher10clearErrorEv
    ...
    _lilu_os_log
  (expected from as.vit9696.Lilu, which is not in the collection)
link check ok
```

Exit status 1 when a symbol is exported by nobody, or by a bundle the kext does not declare (that line says `NOT IN OSBundleLibraries`). Lilu and other kexts OpenCore injects next to yours are not in the collection, so name them with `--own-lib`: their symbols are listed instead of failing the check. `--baseline OTHER.kext` takes a kext you know loads; symbols it lacks too are reported as expected. `--kc PATH` checks against another collection, for example one copied from a different macOS build.

### Look at a class

```python
import sys; sys.path.insert(0, '/path/to/kcabi')
from kcfile import KC
from disasm import Disassembler

kc = KC('/System/Library/KernelCollections/BootKernelExtensions.kc')
hex(kc.metaclass_size('IO80211Controller'))       # '0x128' on 25G241
for slot, raw, target, name in kc.vtable('IO80211Controller')[:12]:
    print(slot, name)

dis = Disassembler(kc, '/tmp/kcabi-cache')
print('\n'.join(dis.function(kc.find('__ZN17IO80211Controller5startEP9IOService'))))
```

### Dump one build, compare two

```
python3 dump.py                                   # -> ./dumps/<build>
python3 dump.py --ref ~/src/ga403wm-hackintosh/abi/native-wifi/24H32 --out dumps/25G241
python3 compare.py dumps/24H32 dumps/25G241       # -> dumps/25G241/compare/summary.txt
```

A dump of 25G241 takes about 8 seconds and is 4 MB. `--ref` points at an older dump whose disassembled functions are dumped again under the same names (renamed ones are matched by their qualified name); without it only `functions-extra.txt` and the MetaClass constructors are disassembled.

### Headers and the update check

```
python3 genhdr.py gen   dumps/25G241 include/abi --iface-class MyWlanIf --impl src/MyWlanIf.cpp
python3 genhdr.py check dumps/25G241 include/abi
python3 genhdr.py check-native dumps/25G241 MyWlanIf AppleBCMWLANSkywalkInterface src/MyWlanIf.cpp -- <your clang flags>
python3 refresh.py --old 25G241 -- ./build.sh    # after a macOS update, on the updated system
```

`check` prints one line per class (`slots apple=... clang=... mismatches=0`) and ends with `headers verified`. `refresh.py` exits 0 when the ABI is unchanged, 3 when slots or sizes moved, 4 when the request tables or a watched function changed. The stub file `genhdr.py gen` writes (`iface_stubs.inc`) uses the `MTK_IFACE_DECLS` / `MTK_IFACE_DEFS` macros and the `nativeCall` hook of the MT7925 driver; change `render_stubs()` if your driver routes requests differently.

## Requirements

- Python 3.9 or later (the one in the Xcode Command Line Tools is fine). Standard library only.
- The Command Line Tools for `nm` (link check), `clang++`, `c++filt` and the Kernel.framework headers (genhdr).
- `llvm-objdump` for `disasm.py`, `dump.py` and `refresh.py`. It is looked up in `$LLVM_OBJDUMP`, then the MacPorts llvm-20 paths `/opt/local/libexec/llvm-20/bin/llvm-objdump` and `/opt/local/bin/llvm-objdump-mp-20`. Other LLVM builds should work if you point `LLVM_OBJDUMP` at them; only MacPorts llvm 20 has been tested.
- x86_64 collections only. Apple Silicon kernel caches use a different pointer format and are not handled.

Environment variables, all optional:

| Variable | Used by | Default |
|---|---|---|
| `KCABI_KC` | linkcheck.py | `/System/Library/KernelCollections/BootKernelExtensions.kc` |
| `LLVM_OBJDUMP` | disasm.py | the MacPorts paths above |
| `KCABI_CACHE` | dump.py | `~/.cache/kcabi` (carved copies, about 320 MB for one build) |
| `KCABI_REF` | dump.py | none |
| `KCABI_DUMPS` | refresh.py | `./dumps` |
| `KCABI_ROOT` | genhdr.py | the current directory (generated headers name their dump relative to it) |

## Status

Tested on macOS 26.7.1 (25G241), x86_64, on a Hackintosh (Lenovo Legion 5 15IAX10, OpenCore 1.0.8), Python 3.9.6, MacPorts llvm 20:

- `linkcheck.py` on a Lilu plugin: passes with `--own-lib as.vit9696.Lilu`, fails without it on the 8 Lilu symbols, as it should.
- `dump.py` of 25G241: 48 vtables, 329 instance sizes, 417 functions. Comparing it with an earlier dump of the same build gives 418 identical functions and no differences.
- `genhdr.py gen` and `check` on that dump: the 9 headers verify, and they match the headers the MT7925 native driver builds against.
- `refresh.py` from a macOS 15 (24H32) dump to 25G241: verdict review (request tables grew from 561 to 586 IDs, Skywalk classes grew by 0x10 bytes).
- `dump.py` and `compare.py` on macOS 26.7.2 (25G332), on a boot kernel collection rebuilt from Apple's delta OTA before the update was installed: instance sizes, vtables and the ioctl dispatch tables unchanged from 25G241. The MT7925 native driver built on that result came up on the real 25G332 on 2026-10-28.

Only one machine and three builds have been through it. Reports from other builds are welcome (see CONTRIBUTING.md).

## How it works

How the collection is parsed, how vtables and sizes are read, and how the link check decides: [docs/HOW-IT-WORKS.md](docs/HOW-IT-WORKS.md).

## Credits

- **ga403wm-hackintosh** (thanhnndev and contributors, BSD-3-Clause-Clear): the method of reading a kernel collection (`tools/kc.py`, `docs/IO80211-ABI-2.md`), the link check idea (`tools/check_kext_links.py`), and the header generation method and return type tables in `genhdr.py` (`tools/io80211_abi.py`, `gen_io80211_header.py`, `io80211_check.py`, `gen_native_iface.py`, `check_native_slots.py`). See [NOTICE.md](NOTICE.md).

## Licence

ISC, see [LICENSE](LICENSE). `genhdr.py` adapts code from ga403wm-hackintosh, which is BSD-3-Clause-Clear; that licence is in `LICENSES/` and applies to the adapted parts as well.
