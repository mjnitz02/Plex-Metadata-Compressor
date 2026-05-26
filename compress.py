#!/usr/bin/env python3
import json
import os
import stat as stat_module
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageFile

ImageFile.LOAD_TRUNCATED_IMAGES = True

JPEG_MAGIC = b'\xff\xd8\xff'
PNG_MAGIC = b'\x89PNG'
STATE_FILE = '.compress_state.json'
JPEG_QUALITY = 75
STATE_SAVE_INTERVAL = 500


def load_state(metadata_dir: Path) -> dict:
    state_path = metadata_dir / STATE_FILE
    try:
        return json.loads(state_path.read_text())
    except Exception:
        return {}


def save_state(metadata_dir: Path, state: dict) -> None:
    (metadata_dir / STATE_FILE).write_text(json.dumps(state, indent=2))


def file_key(path: Path, metadata_dir: Path) -> str:
    return str(path.relative_to(metadata_dir))


def already_processed(path: Path, metadata_dir: Path, state: dict) -> bool:
    entry = state.get(file_key(path, metadata_dir))
    if not entry:
        return False
    try:
        stat = path.stat()
        return entry.get('size') == stat.st_size and entry.get('mtime') == stat.st_mtime
    except OSError:
        return False


def record_processed(path: Path, metadata_dir: Path, state: dict) -> None:
    try:
        stat = path.stat()
        state[file_key(path, metadata_dir)] = {'size': stat.st_size, 'mtime': stat.st_mtime}
    except OSError:
        pass


def detect_type(path: Path) -> str | None:
    try:
        header = path.read_bytes()[:4]
    except OSError:
        return None
    if header[:3] == JPEG_MAGIC:
        return 'jpeg'
    if header == PNG_MAGIC:
        return 'png'
    return None


def restore_stat(path: Path, st: os.stat_result) -> None:
    try:
        os.chown(path, st.st_uid, st.st_gid)
        os.chmod(path, stat_module.S_IMODE(st.st_mode))
    except OSError as e:
        print(f'  Warning: could not restore permissions on {path.name}: {e}', flush=True)


def fmt_bytes(n: int) -> str:
    if n < 1024:
        return f'{n} B'
    if n < 1024 ** 2:
        return f'{n / 1024:.1f} KB'
    return f'{n / 1024 ** 2:.1f} MB'


def compress_jpeg(path: Path) -> int:
    original_stat = path.stat()
    original_size = original_stat.st_size
    try:
        with Image.open(path) as img:
            mode = img.mode
            if mode in ('RGBA', 'P', 'LA'):
                img = img.convert('RGB')
            elif mode == 'CMYK':
                img = img.convert('RGB')
            with tempfile.NamedTemporaryFile(dir=path.parent, suffix='.tmp', delete=False) as tmp:
                tmp_path = Path(tmp.name)
            try:
                img.save(tmp_path, 'JPEG', quality=JPEG_QUALITY, optimize=True, progressive=True)
                new_size = tmp_path.stat().st_size
                if new_size < original_size:
                    tmp_path.replace(path)
                    restore_stat(path, original_stat)
                    return original_size - new_size
                else:
                    return 0
            finally:
                tmp_path.unlink(missing_ok=True)
    except Exception as e:
        print(f'  JPEG error {path.name}: {e}', flush=True)
        return 0


def compress_png(path: Path) -> int:
    original_stat = path.stat()
    original_size = original_stat.st_size
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix='.tmp', delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        result = subprocess.run(
            [
                'pngquant', '--force', '--skip-if-larger',
                '--quality', '60-85',
                '--output', str(tmp_path),
                '--', str(path),
            ],
            capture_output=True,
        )
        # exit 98 = skipped because output would be larger; 0 = success
        if result.returncode in (0, 98) and tmp_path.exists():
            new_size = tmp_path.stat().st_size
            if new_size > 0 and new_size < original_size:
                tmp_path.replace(path)
                restore_stat(path, original_stat)
                return original_size - new_size
        return 0
    except FileNotFoundError:
        print('  pngquant not found — skipping PNG compression', flush=True)
        return 0
    finally:
        tmp_path.unlink(missing_ok=True)


def walk_images(metadata_dir: Path):
    for dirpath, dirnames, filenames in os.walk(metadata_dir):
        # themes directories contain MP3 audio — skip entirely
        dirnames[:] = [d for d in dirnames if d != 'themes']
        dp = Path(dirpath)
        for filename in sorted(filenames):
            if filename.startswith('.'):
                continue
            yield dp / filename


def main() -> None:
    if len(sys.argv) < 2:
        print('Usage: compress.py <metadata_dir>', flush=True)
        sys.exit(1)

    metadata_dir = Path(sys.argv[1]).resolve()
    if not metadata_dir.is_dir():
        print(f'Not a directory: {metadata_dir}', flush=True)
        sys.exit(1)

    print(f'[plex-compressor] Scanning: {metadata_dir}', flush=True)
    state = load_state(metadata_dir)

    files = list(walk_images(metadata_dir))
    total = len(files)
    print(f'[plex-compressor] Found {total} candidate files', flush=True)

    scanned = skipped = compressed = 0
    total_saved = 0

    for i, path in enumerate(files, 1):
        img_type = detect_type(path)
        if img_type is None:
            continue

        scanned += 1

        if already_processed(path, metadata_dir, state):
            skipped += 1
            continue

        original_size = path.stat().st_size
        saved = compress_jpeg(path) if img_type == 'jpeg' else compress_png(path)

        if saved > 0:
            compressed += 1
            total_saved += saved
            print(
                f'  [{i}/{total}] {img_type.upper()} {path.name}: '
                f'{fmt_bytes(original_size)} -> {fmt_bytes(original_size - saved)} '
                f'(saved {fmt_bytes(saved)})',
                flush=True,
            )

        record_processed(path, metadata_dir, state)

        if scanned % STATE_SAVE_INTERVAL == 0:
            save_state(metadata_dir, state)

    save_state(metadata_dir, state)
    print(
        f'\n[plex-compressor] Done — scanned: {scanned}, skipped: {skipped}, '
        f'compressed: {compressed}, saved: {fmt_bytes(total_saved)}',
        flush=True,
    )


if __name__ == '__main__':
    main()
