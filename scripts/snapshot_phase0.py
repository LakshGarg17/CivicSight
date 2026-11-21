"""Phase 0 Backup and Snapshot Script.
Zips project excluding node_modules, .venv, Dataset, and runs folders to a location outside the repo.
Also takes a snapshot copy of the active database.
"""
import os
import shutil
import zipfile
from pathlib import Path

PROJECT_ROOT = Path("d:/Projects/CivicSight").resolve()
BACKUP_DIR = Path(r"C:\Users\Laksh Garg\.gemini\antigravity\brain\e256f395-bb10-429f-804a-a172a29bae53\scratch\backups").resolve()
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

BACKUP_ZIP = BACKUP_DIR / "civicsight_pre_integration_audit.zip"
DB_BACKUP = BACKUP_DIR / "civicsight_db_backup.sqlite"

# 1. Backup SQLite database if exists
active_db = PROJECT_ROOT / "backend" / "civicsight.db"
if active_db.is_file():
    shutil.copy2(active_db, DB_BACKUP)
    print(f"Database backed up to: {DB_BACKUP} ({DB_BACKUP.stat().st_size} bytes)")
else:
    print("No active SQLite database file found.")

# 2. Exclude patterns
EXCLUDE_DIRS = {
    "node_modules",
    ".venv",
    ".venv-gpu",
    "venv",
    "env",
    "Dataset",
    "runs",
    ".pytest_cache",
    ".chrome_debug",
    "htmlcov",
    ".git",
}

print(f"Creating project backup zip at {BACKUP_ZIP}...")
count = 0
with zipfile.ZipFile(BACKUP_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(PROJECT_ROOT):
        # prune excluded directories
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in files:
            # Skip large weights or temp files
            if f.endswith((".pt", ".pyc", ".pyo")):
                continue
            full_path = Path(root) / f
            rel_path = full_path.relative_to(PROJECT_ROOT)
            zf.write(full_path, arcname=str(rel_path))
            count += 1

print(f"Backup zip complete: {BACKUP_ZIP} ({count} files, {BACKUP_ZIP.stat().st_size} bytes)")
