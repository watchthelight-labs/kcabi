#!/usr/bin/env python3
# <wtl> project: kcabi | file: gfxdump.py | author: watchthelight </wtl>
# SPDX-License-Identifier: ISC
"""
Dump the graphics-side ABI a third-party GPU driver depends on: vtables, method lists and instance sizes of the
IOAcceleratorFamily2, IOGraphicsFamily and IOSurface classes, from both kernel collections of one build.
Read-only, same output layout as dump.py, so compare.py diffs two builds.

usage: gfxdump.py [--kcdir DIR] [--build BUILD] [--out DIR]

  --kcdir  directory holding BootKernelExtensions.kc and SystemKernelExtensions.kc
           (default: /System/Library/KernelCollections, the running system)
  --build  label for the output (default: the running build from sw_vers)
  --out    output directory (default: ./dumps-gfx/<build>)
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dump  # noqa: E402
from kcfile import KC  # noqa: E402

PREFIXES = ('IOAccel', 'IOGraphicsAccelerator', 'IOFramebuffer', 'IONDRV', 'IODisplay', 'IOSurface',
            'IOGraphicsDevice', 'IOBootFramebuffer', 'AppleGraphicsDeviceControl', 'AppleGraphicsControl')
FAMILIES = ('com.apple.iokit.IOAcceleratorFamily2', 'com.apple.iokit.IOGraphicsFamily', 'com.apple.iokit.IOSurface',
            'com.apple.iokit.IONDRVSupport', 'com.apple.driver.AppleGraphicsDeviceControl')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--kcdir', default='/System/Library/KernelCollections')
    ap.add_argument('--build')
    ap.add_argument('--out')
    a = ap.parse_args()
    build = a.build or subprocess.run(['sw_vers', '-buildVersion'], capture_output=True, text=True).stdout.strip()
    out = a.out or os.path.join(os.getcwd(), 'dumps-gfx', build)
    os.makedirs(out, exist_ok=True)
    dump.SIZE_FAMILIES = FAMILIES
    spans, sizes, src = {}, {}, {'build': build, 'collections': {}, 'tool': 'kcabi/gfxdump.py'}
    for name in ('BootKernelExtensions.kc', 'SystemKernelExtensions.kc'):
        path = os.path.join(a.kcdir, name)
        if not os.path.exists(path):
            continue
        kc = KC(path)
        classes = sorted(c for c in kc.classes() if c.startswith(PREFIXES))
        spans.update(dump.dump_vtables(kc, out, classes))
        part = os.path.join(out, 'sizes.%s.txt' % name.split('Kernel')[0].lower())
        sizes.update(dump.dump_sizes(kc, out))
        os.replace(os.path.join(out, 'sizes.txt'), part)
        src['collections'][name] = {'sha256': kc.sha256(), 'classes': len(classes),
                                    'entries': {b: '%#x' % vm for b, vm, _ in kc.entries if b in FAMILIES}}
    with open(os.path.join(out, 'sizes.txt'), 'w') as f:
        for part in sorted(p for p in os.listdir(out) if p.startswith('sizes.') and p != 'sizes.txt'):
            f.write(open(os.path.join(out, part)).read())
    src['vtables_symbol_spans'] = spans
    with open(os.path.join(out, 'source.json'), 'w') as f:
        json.dump(src, f, indent=2)
    print('wrote %s: %d vtables, %d sizes' % (out, sum(1 for v in spans.values() if v), len(sizes)))


if __name__ == '__main__':
    main()
