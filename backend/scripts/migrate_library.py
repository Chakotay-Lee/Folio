"""
One-time migration script: moves all library data into Books/.folio/
and reorganizes book files into Books/<genre>/ directory structure.

Usage:
  python -m backend.scripts.migrate_library [--dry-run] [--config PATH]
"""
import argparse
import shutil
import sqlite3
import sys
from pathlib import Path


def sanitize_path_segment(s: str) -> str:
    illegal = r'/:\x00<>|?*"\\'
    for ch in illegal:
        s = s.replace(ch, '_')
    return s.strip().strip('.')


def genre_to_dir(genre_path: str | None) -> Path:
    if not genre_path or not genre_path.strip():
        return Path('未分類')
    parts = [p.strip() for p in genre_path.split(' > ') if p.strip()][:3]
    sanitized = [sanitize_path_segment(p) for p in parts if sanitize_path_segment(p)]
    return Path(*sanitized) if sanitized else Path('未分類')


def unique_dest(dest: Path) -> Path:
    if not dest.exists():
        return dest
    stem, suffix = dest.stem, dest.suffix
    i = 2
    while True:
        candidate = dest.parent / f"{stem}_{i}{suffix}"
        if not candidate.exists():
            return candidate
        i += 1


def migrate(config_path: Path, dry_run: bool) -> None:
    import json

    raw = json.loads(config_path.read_text(encoding='utf-8'))
    s = raw['storage_paths']

    books_root = Path(s.get('books_root', '')).expanduser().resolve()
    if not books_root or str(books_root) == str(Path('.').resolve()):
        print("ERROR: books_root not set in config.json", file=sys.stderr)
        sys.exit(1)

    folio_dir = books_root / '.folio'
    app_dir = config_path.parent

    label = '[DRY-RUN] ' if dry_run else ''

    # ── Step 1: Move system data to .folio/ ────────────────────────────────
    print(f"\n=== Step 1: Move system data → {folio_dir} ===")
    if not dry_run:
        folio_dir.mkdir(parents=True, exist_ok=True)

    data_items = [
        (app_dir / 'library_core.db',    folio_dir / 'library_core.db'),
        (app_dir / 'library_core.db-shm', folio_dir / 'library_core.db-shm'),
        (app_dir / 'library_core.db-wal', folio_dir / 'library_core.db-wal'),
        (app_dir / 'user_activity.db',    folio_dir / 'user_activity.db'),
        (app_dir / 'user_activity.db-shm', folio_dir / 'user_activity.db-shm'),
        (app_dir / 'user_activity.db-wal', folio_dir / 'user_activity.db-wal'),
        (app_dir / 'vector_store',        folio_dir / 'vector_store'),
        (app_dir / 'assets',              folio_dir / 'assets'),
    ]

    # Checkpoint WAL on source DBs before moving so all data is in the main file
    for db_candidate in [app_dir / 'library_core.db', app_dir / 'user_activity.db']:
        if db_candidate.exists():
            try:
                c = sqlite3.connect(str(db_candidate))
                c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                c.close()
                if not dry_run:
                    print(f"  Checkpointed WAL: {db_candidate.name}")
            except Exception as e:
                print(f"  WARNING: WAL checkpoint failed for {db_candidate.name}: {e}")

    for src, dst in data_items:
        if not src.exists():
            continue
        # For DB files: skip only if destination has actual data
        if dst.exists():
            if dst.suffix == '.db':
                try:
                    c = sqlite3.connect(str(dst))
                    tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
                    has_data = False
                    if 'books' in tables:
                        count = c.execute("SELECT count(*) FROM books").fetchone()[0]
                        has_data = count > 0
                    c.close()
                    if has_data:
                        print(f"  SKIP (destination DB has {count} books): {dst}")
                        continue
                    print(f"  {label}REPLACE empty DB: {dst}")
                except Exception:
                    print(f"  {label}REPLACE unreadable DB: {dst}")
            elif dst.is_dir() and any(dst.iterdir()):
                print(f"  SKIP (destination dir has data): {dst}")
                continue
            else:
                print(f"  {label}REPLACE empty: {dst}")
            if not dry_run:
                if dst.is_dir():
                    shutil.rmtree(str(dst))
                else:
                    dst.unlink(missing_ok=True)
        print(f"  {label}MOVE {src} → {dst}")
        if not dry_run:
            if src.is_dir():
                shutil.copytree(str(src), str(dst))
                shutil.rmtree(str(src))
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dst))

    # ── Step 2: Update relative_path in DB ─────────────────────────────────
    print(f"\n=== Step 2: Update relative_path in DB ===")

    def _find_active_db() -> Path | None:
        for candidate in [folio_dir / 'library_core.db', app_dir / 'library_core.db']:
            if candidate.exists():
                try:
                    c = sqlite3.connect(str(candidate))
                    cnt = c.execute("SELECT count(*) FROM books").fetchone()[0]
                    c.close()
                    if cnt > 0:
                        return candidate
                except Exception:
                    pass
        return None

    db_path = _find_active_db()
    if not db_path:
        print("  SKIP: no library_core.db with data found")
    else:
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        cur.execute("SELECT id, relative_path, genre_path FROM books")
        rows = cur.fetchall()
        updates = []
        for uuid, rel_path, genre_path in rows:
            p = Path(rel_path)
            if p.is_absolute():
                try:
                    new_rel = str(p.relative_to(books_root))
                except ValueError:
                    new_rel = p.name  # fallback: just filename
                print(f"  {label}UPDATE {rel_path} → {new_rel}")
                updates.append((new_rel, uuid))
            else:
                print(f"  SKIP (already relative): {rel_path}")
        if not dry_run and updates:
            cur.executemany("UPDATE books SET relative_path=? WHERE id=?", updates)
            conn.commit()
        conn.close()

    # ── Step 3: Move book files into Books/<genre>/ ─────────────────────────
    print(f"\n=== Step 3: Move book files into {books_root}/<genre>/ ===")
    db_path = _find_active_db()
    if not db_path:
        print("  SKIP: no library_core.db with data found")
        return

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("SELECT id, relative_path, genre_path FROM books")
    rows = cur.fetchall()
    path_updates = []

    for uuid, rel_path, genre_path in rows:
        p = Path(rel_path)
        src = p if p.is_absolute() else (books_root / p)
        genre_dir = genre_to_dir(genre_path)
        dest_dir = books_root / genre_dir
        dest = dest_dir / src.name

        # Already in the right place
        try:
            dest.relative_to(books_root)
            if src.resolve() == dest.resolve():
                print(f"  SKIP (already in place): {rel_path}")
                continue
        except ValueError:
            pass

        if not src.exists():
            print(f"  SKIP (file missing): {src}")
            continue

        dest = unique_dest(dest)
        new_rel = str(dest.relative_to(books_root))
        print(f"  {label}MOVE {src} → {dest}  (rel: {new_rel})")
        path_updates.append((new_rel, uuid, dest))

        if not dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dest))

    if not dry_run and path_updates:
        cur.executemany("UPDATE books SET relative_path=? WHERE id=?",
                        [(r, u) for r, u, _ in path_updates])
        conn.commit()

        # Clean up empty source dirs
        for _, _, dest in path_updates:
            _cleanup_empty_dirs(dest.parent.parent, books_root)

    conn.close()

    print(f"\n{'[DRY-RUN] ' if dry_run else ''}Migration complete.")


def _cleanup_empty_dirs(start: Path, stop: Path) -> None:
    p = start
    while p != stop and p.is_dir():
        try:
            p.rmdir()
            p = p.parent
        except OSError:
            break


def main() -> None:
    parser = argparse.ArgumentParser(description='Migrate Folio library data to Books/.folio/')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--config', default='./config.json', help='Path to config.json')
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    if not config_path.exists():
        print(f"ERROR: config.json not found at {config_path}", file=sys.stderr)
        sys.exit(1)

    migrate(config_path, dry_run=args.dry_run)


if __name__ == '__main__':
    main()
