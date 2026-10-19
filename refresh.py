#!/usr/bin/env python3
# <wtl> project: kcabi | file: refresh.py | author: watchthelight </wtl>
# SPDX-License-Identifier: ISC
# The command to run after a macOS update, on the updated system. It dumps the new build's IO80211 / IOSkywalk ABI
# (dump.py), compares it with the build your kext was last verified against (compare.py) and prints a verdict:
#   unchanged  the classes genhdr.py generates headers for keep their vtables and the guarded classes their sizes:
#              regenerated headers differ only in the banner;
#   relayout   slots or sizes moved: regenerate the headers and rebuild; request IDs, event layouts and struct
#              sizes are not checked here, so read the compare notes before the first boot;
#   review     the apple80211 request tables or one of the watched functions changed: rebuild if you like, but do
#              not enable the kext until a person has read the changed functions.
# With a command after `--` it then runs that command (your build script), with KCABI_OLD, KCABI_NEW and
# KCABI_VERDICT in its environment.
"""
usage: refresh.py --old BUILD [--new BUILD] [--dumps DIR] [--kc PATH] [--stubs FILE] [-- BUILD_COMMAND...]

  --old    the build your kext is verified for; its dump must be in DUMPS/<old> (default: the only other
           build in DUMPS, if there is exactly one)
  --new    the build to refresh for (default: sw_vers -buildVersion); its dump is made if missing
  --dumps  directory holding one dump per build (default: $KCABI_DUMPS or ./dumps, the same as dump.py)
  --kc     the new build's kernel collection (default: the running one)
  --stubs  your iface_stubs.inc for the old build, passed to compare.py
The comparison is written to DUMPS/<new>/compare-<old>. Exit status: 0 unchanged, 3 relayout, 4 review,
1 on errors, or the build command's status when it fails.
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
sys.path.insert(0, HERE)
from genhdr import ORDER, GUARD_CLASSES  # noqa: E402

# functions a native Wi-Fi front end's payload layouts were read from: a change here is a review item
WATCH_FUNCTIONS = ('scanResultEventHandler', 'updateOrAddBeacon', 'setCurrentBSS', 'updateBss', 'linkStatusInd',
                   'setWCL_ASSOCIATE', 'setWCL_SCAN_REQ', 'getWCL_BSS_INFO', 'getWCL_EXTENDED_BSS_INFO', 'handleJoinRequest',
                   'getCARD_CAPABILITIES', 'initRegistrationInfo', 'registerInfraEthernetInterface', 'IO80211Controller::start',
                   'IO80211SkywalkInterface::start', 'IO80211InfraInterface::start')
EXIT = {'unchanged': 0, 'relayout': 3, 'review': 4}


def sh(cmd, **kw):
    print('+ ' + ' '.join(cmd), flush=True)
    return subprocess.run(cmd, **kw)


def verdict(compare_dir):
    summary = open(os.path.join(compare_dir, 'summary.txt')).read().splitlines()
    section, vt_changed, size_changed, dispatch, fn_changed = '', [], [], [], []
    for line in summary:
        if line.startswith('## '):
            section = line[3:]
            continue
        if section.startswith('instance sizes') and line.strip():
            cls = line.split('\t')[0].strip()
            if cls in GUARD_CLASSES:
                size_changed.append(line.strip())
        elif section.startswith('vtables'):
            m = re.match(r'\s+(\S+)\s+(.*)$', line)
            if m and m.group(1) in ORDER and m.group(2) != 'unchanged':
                vt_changed.append('%s: %s' % (m.group(1), m.group(2)))
        elif section.startswith('apple80211 request tables') and 'differ' in line and ' 0 IDs differ' not in line:
            dispatch.append(line.strip())
        elif section.startswith('disassembled') and line.strip():
            fn_changed.append(line.strip())
    watched = []
    fpath = os.path.join(compare_dir, 'functions.txt')
    if os.path.exists(fpath):
        for line in open(fpath):
            if 'changed' in line.lower() and any(w in line for w in WATCH_FUNCTIONS):
                watched.append(line.strip()[:160])
    if not vt_changed and not size_changed and not dispatch and not watched:
        kind = 'unchanged'
    elif watched or dispatch:
        kind = 'review'
    else:
        kind = 'relayout'
    return kind, vt_changed, size_changed, dispatch, watched


def main(argv):
    build_cmd = []
    if '--' in argv:
        i = argv.index('--')
        argv, build_cmd = argv[:i], argv[i + 1:]
    old = new = kc = stubs = None
    dumps = os.environ.get('KCABI_DUMPS') or os.path.join(os.getcwd(), 'dumps')
    args = list(argv)
    while args:
        if args[0] in ('-h', '--help'):
            print(__doc__.strip())
            return 0
        if args[0] in ('--old', '--new', '--dumps', '--kc', '--stubs') and len(args) > 1:
            val = args[1]
            if args[0] == '--old':
                old = val
            elif args[0] == '--new':
                new = val
            elif args[0] == '--dumps':
                dumps = val
            elif args[0] == '--kc':
                kc = val
            else:
                stubs = val
            args = args[2:]
        else:
            sys.exit(__doc__)
    dumps = os.path.abspath(dumps)
    new = new or subprocess.run(['sw_vers', '-buildVersion'], capture_output=True, text=True, check=True).stdout.strip()
    if not old:
        others = sorted(d for d in os.listdir(dumps) if d != new and os.path.isdir(os.path.join(dumps, d))) \
            if os.path.isdir(dumps) else []
        if len(others) != 1:
            sys.exit('give --old: %s holds %s' % (dumps, ', '.join(others) or 'no other build'))
        old = others[0]
    old_dir, new_dir = os.path.join(dumps, old), os.path.join(dumps, new)
    print('verified build %s, target build %s' % (old, new))
    if not os.path.isdir(old_dir):
        sys.exit('no dump for the verified build at %s' % old_dir)
    if not os.path.isdir(new_dir):
        cmd = [PY, '-I', os.path.join(HERE, 'dump.py'), '--out', new_dir]
        if kc:
            cmd += ['--kc', kc]
        if sh(cmd).returncode:
            sys.exit('dump failed')
    compare_dir = os.path.join(new_dir, 'compare-%s' % old)
    cmd = [PY, '-I', os.path.join(HERE, 'compare.py'), old_dir, new_dir, '--out', compare_dir]
    if stubs:
        cmd += ['--stubs', stubs]
    if sh(cmd, capture_output=True).returncode:
        sys.exit('compare failed')
    kind, vt, sizes, dispatch, watched = verdict(compare_dir)
    print('\nverdict for %s -> %s: %s' % (old, new, kind.upper()))
    for x in vt:
        print('  vtable   ' + x)
    for x in sizes:
        print('  size     ' + x)
    for x in dispatch:
        print('  dispatch ' + x)
    for x in watched:
        print('  function ' + x)
    print('  details: %s' % compare_dir)
    if old == new:
        print('  (same build on both sides: this only tests the pipeline)')
    if build_cmd:
        env = dict(os.environ, KCABI_OLD=old, KCABI_NEW=new, KCABI_VERDICT=kind)
        r = sh(build_cmd, env=env)
        if r.returncode:
            print('build command failed (%d): the new build needs hand work' % r.returncode)
            return r.returncode
    if kind == 'relayout':
        print('\nslots or sizes moved: regenerate the headers (genhdr.py gen) and read the compare notes before booting.')
    elif kind == 'review':
        print('\nthe request tables or watched functions changed: keep the kext disabled until they have been read.')
    return EXIT[kind]


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
