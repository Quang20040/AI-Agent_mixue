"""Restore a backup zip made by the app (Quản lý nhân viên → Sao lưu dữ liệu, or GET /api/v1/stores/{id}/backup).

    python scripts/restore_export.py backup.zip            # check only
    python scripts/restore_export.py backup.zip --apply    # restore (stop the app first)

Every file is checked against the manifest first; existing files are kept as <name>.before-restore.
Run it with the same environment as the app (PERSIST_DIR / DATABASE_URL …) so the live paths are used.
"""
import argparse
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.engine.data_export import sources, verify  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('zip', type=Path)
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    bad = verify(args.zip)
    if bad:
        sys.exit(f'Checksum mismatch, nothing restored: {bad[:5]}')
    targets = sources()
    with zipfile.ZipFile(args.zip) as zf:
        names = [n for n in zf.namelist() if n != 'manifest.json']
        plan = []
        for name in names:
            base = next((k for k in sorted(targets, key=len, reverse=True) if name == k or name.startswith(k + '/')), None)
            if base is None:
                print('skip (unknown):', name)
                continue
            dest = targets[base] if name == base else targets[base] / name[len(base) + 1:]
            plan.append((name, dest))
        for name, dest in plan:
            print(('restore ' if args.apply else 'would restore ') + f'{name} -> {dest}')
            if args.apply:
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.exists():
                    shutil.copy2(dest, dest.with_name(dest.name + '.before-restore'))
                dest.write_bytes(zf.read(name))
    print(f'{len(plan)} files {"restored" if args.apply else "checked"}.')


if __name__ == '__main__':
    main()
