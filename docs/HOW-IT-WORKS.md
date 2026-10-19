# How it works

## The collection

Since macOS 11 the kernel and the kexts it boots with are linked ahead of time into one file, `/System/Library/KernelCollections/BootKernelExtensions.kc`. On x86_64 it is a 64-bit Mach-O of type `MH_FILESET`. Its top-level load commands are segments plus one `LC_FILESET_ENTRY` (0x80000035) per member: the kernel (`com.apple.kernel`) and every boot kext. Each entry gives a bundle id, a virtual address and a file offset.

At that file offset sits the member's own Mach-O header. Its load commands (segments, `LC_SYMTAB`) use file offsets that count from the start of the whole collection, not from the member. `kcfile.py` walks the top-level header first, then every member header, and records:

- the top-level segments, used to turn a virtual address into a file offset (`va2off`);
- each member's segments, used to say which bundle an address belongs to (`owner`);
- each member's symbol table.

Symbols are read from every `LC_SYMTAB`. A 16-byte `nlist_64` is kept when it is not a debugging entry (`n_type & 0xe0 == 0`), is defined in a section (`n_type & 0x0e == N_SECT`) and has a non-zero value. Local and external symbols both count for lookups. When two names share an address, a C++ mangled name (`__Z...`) wins over a plain one, because the mangled name carries the class and the parameter types.

## Pointers

Pointers inside the collection are stored in the kernel-cache form of dyld's chained fixups (`DYLD_CHAINED_PTR_X86_64_KERNEL_CACHE`): the low 30 bits are an offset from the collection's base address, the lowest segment address. `KC.ptr()` returns `base + (raw & 0x3fffffff)`. A value whose top 24 bits are `0xffffff` is already an absolute kernel address and is returned as it is. Only cache level 0 (the boot collection itself) is handled, which is all a boot kext's vtable points into.

## Classes

- **Vtable**: the words from the `__ZTV<len><Class>` symbol up to the next symbol. Words 0 and 1 are the C++ ABI header (offset to top, RTTI, which is 0 in the kernel), so slot N is at byte N * 8 of the symbol and at N * 8 - 0x10 from an object's vtable pointer. Every word is decoded with `ptr()` and named from the symbol table; an unimplemented pure virtual shows as `___cxa_pure_virtual`.
- **Instance size**: libkern classes pass their size to `OSMetaClass::OSMetaClass(name, super, size)` from `<Class>::MetaClass::MetaClass()`. `metaclass_size()` scans that constructor's bytes for the last `mov ecx, imm32` (opcode `B9`) before a `call` (`E8`) whose target is an `OSMetaClass` constructor, and returns the immediate. It reads machine code, not disassembly, so it needs no objdump.
- **Methods**: every symbol whose mangled name starts with the class's qualified prefix.

## Disassembly

`llvm-objdump` only disassembles a normal Mach-O, and a member's load commands only make sense with the whole collection behind them. `KC.carve()` therefore writes a copy of the collection whose first bytes are the member's own header; everything after the header is the collection unchanged, so the absolute file offsets stay valid. One copy is as large as the collection (about 65 MB on 25G241) and is reused while it matches. `disasm.py` runs `llvm-objdump -d -M intel --no-show-raw-insn` on it, once per bundle for the small kexts and per function (`--start-address`, `--stop-address`) for the kernel.

Each instruction gets a note: for a `[rip + disp]` operand the target is read, and shown as a string if it is printable ASCII, otherwise as a symbol; for a direct call or jump, the target's symbol. `normalise()` removes everything that moves between builds without meaning anything (addresses, rip displacements, local branch targets) so `compare.py` can tell whether two builds run the same instructions with the same field offsets and the same callees.

## What the dump holds

`dump.py` writes, for one build:

- `<Class>.vtable.txt` and `<Class>.methods.txt` for the classes listed at the top of the file;
- `sizes.txt`, the MetaClass size of every class owned by the Wi-Fi, Skywalk, corecapture and networking families;
- `dispatch/ioctl-get-dispatch.txt` and `ioctl-set-dispatch.txt`: `apple80211RouteInternal` indexes two handler tables by request ID - 1. The dump finds the tables from the function's `lea reg, [rip + ...]` operands, the request limit from its bounds check, and tells GET from SET by the handler names;
- `callbacks/`: the `g<Manager>CallBackArray` tables of IO80211Family's WCL managers. Each entry is 0x18 bytes, a bulletin id (`event code << 16 | 2`) and a C++ member function pointer;
- `asm/`, the disassembly of the reference list, `functions-extra.txt` and the MetaClass constructors, with `INDEX.txt` and `missing-functions.txt`;
- `source.json`: the collection's SHA-256, product version, build, kernel version string and the versions of the family kexts.

## How the link check decides

1. Read the kext's `Info.plist` for `CFBundleExecutable` and `OSBundleLibraries`.
2. Run `nm -um` on the executable and keep every `(undefined) external` symbol.
3. Build the export table of the collection: every symbol that passes the filter above and also has `N_EXT` set. If two bundles export the same name, the first one read wins.
4. For each undefined symbol, look up its owner:
   - owner `com.apple.kernel` (or a bundle id starting with it): ok, whatever `com.apple.kpi.*` bundles the kext declares;
   - owner listed in `OSBundleLibraries`: ok;
   - any other owner: counted as a failure and shown as `NOT IN OSBundleLibraries`;
   - no owner: the symbol is not exported by anything in the collection.
5. Symbols with no owner are dropped when the `--baseline` kext lacks them too (the SDK can still name a slot `_RESERVED...` that the kernel has filled; the linker resolves those from the parent vtable). The rest fail the check, unless the kext declares one of the `--own-lib` bundles: then they are listed as expected from that library, because a kext that OpenCore injects (Lilu, your own core kext) is never in the collection on disk.

What it does not check: which KPI symbol set (`com.apple.kpi.private`, `com.apple.kpi.iokit` and so on) exports a kernel symbol, `OSBundleCompatibleVersion` of the libraries, the System and Auxiliary collections, and symbols that only `--own-lib` libraries would provide (they are listed, not resolved). A pass means the names exist, not that their signatures match the headers you built with.

## How genhdr checks its headers

`genhdr.py gen` names every slot from Apple's own vtable symbols. A pure virtual slot is named by the first derived class in the dump that implements it (for example `AppleBCMWLANSkywalkInterface` for `IO80211SkywalkInterface`). Return types are not part of a mangled name; they come from the SDK header that declares an inherited virtual, from a table of return types read off call sites, or from a guess by name, and each guessed one is tagged `ret: guess` in the header. Each header ends with a `static_assert` on the MetaClass size, padding the class with an opaque byte array.

`genhdr.py check` writes a probe subclass of each class that overrides every pure slot, compiles it with the kext flags and `-Xclang -fdump-vtable-layouts`, and compares clang's slot-by-slot layout with the dump. A mismatch, an extra slot or a compile error fails the check. `check-native` does the same for your own class: it compiles your source and checks that every override lands on the slot where Apple's class has the method of the same name.
