# Contributing

The most useful report is a run on a macOS build I have not tried. Open an issue with the macOS version and build (`sw_vers`), the Mac or Hackintosh, the tool and command line, and its full output. If a tool crashes or a number looks wrong (an instance size, a slot, a request table), say what you expected and where that came from. For `dump.py`, `source.json` from the dump is enough to identify the collection; please don't attach the carved `.macho` copies, they are Apple's binaries.

Pull requests: keep them small and say how you tested them. Support for another family's classes in `dump.py` or `genhdr.py`, Apple Silicon collections, or another LLVM's `llvm-objdump` output are all welcome. I read and test every PR before merging. AI-assisted PRs are fine as long as you can explain the change, which is the same bar I hold my own code to.

Contributions are under the ISC licence, except changes to the parts of `genhdr.py` adapted from ga403wm-hackintosh, which stay BSD-3-Clause-Clear (see NOTICE.md).
