import os
import sys
import shutil
import sqlite3
import zipfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
BACKUP_DIR = Path(r"C:\Users\Laksh Garg\.gemini\antigravity\brain\e256f395-bb10-429f-804a-a172a29bae53\scratch")
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

# 1. Database backup
db_src = BASE_DIR / "backend" / "civicsight.db"
db_dest = BACKUP_DIR / "civicsight_backup_pre_week11.db"
sql_dump_dest = BACKUP_DIR / "civicsight_dump_pre_week11.sql"

if db_src.exists():
    shutil.copy2(db_src, db_dest)
    print(f"Database file copied to: {db_dest} ({os.path.getsize(db_dest)} bytes)")
    
    con = sqlite3.connect(str(db_src))
    with open(sql_dump_dest, "w", encoding="utf-8") as f:
        for line in con.iterdump():
            f.write(f"{line}\n")
    con.close()
    print(f"Database SQL dump written to: {sql_dump_dest} ({os.path.getsize(sql_dump_dest)} bytes)")
else:
    print("Database file not found at:", db_src)

# 2. Project zip archive excluding venv, node_modules, dataset, runs, .git
zip_dest = BACKUP_DIR / "CivicSight_pre_week11_snapshot.zip"
exclude_dirs = {".venv", "node_modules", "dataset", "runs", ".git", "__pycache__"}

print(f"Creating project archive at: {zip_dest} ...")
with zipfile.ZipFile(zip_dest, "w", zipfile.ZIP_DEFLATED) as zipf:
    for root, dirs, files in os.walk(BASE_DIR):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for f in files:
            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, BASE_DIR)
            zipf.write(full_path, rel_path)

print(f"Archive created successfully: {zip_dest} ({os.path.getsize(zip_dest)} bytes)")
