"""
CivicSight Orphan Uploads Cleanup Utility
Safely audits and purges unreferenced image files in backend/uploads/reports and backend/uploads/evidence.
Only deletes files that are NOT referenced in the active database.
"""
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))

from app.db.database import SessionLocal
from app.models.models import Report, RepairEvidence

def audit_and_clean_orphan_uploads(dry_run: bool = True):
    db = SessionLocal()
    reports_dir = BASE_DIR / "backend" / "uploads" / "reports"
    evidence_dir = BASE_DIR / "backend" / "uploads" / "evidence"

    # Query all referenced filenames
    db_report_images = set()
    for (url,) in db.query(Report.image_url).filter(Report.image_url.isnot(None)).all():
        if url:
            db_report_images.add(os.path.basename(url))

    db_evidence_files = set()
    for (path,) in db.query(RepairEvidence.file_path).filter(RepairEvidence.file_path.isnot(None)).all():
        if path:
            db_evidence_files.add(os.path.basename(path))

    db.close()

    disk_reports = set(os.listdir(reports_dir)) if reports_dir.exists() else set()
    disk_evidence = set(os.listdir(evidence_dir)) if evidence_dir.exists() else set()

    orphan_reports = disk_reports - db_report_images
    orphan_evidence = disk_evidence - db_evidence_files

    print(f"Total reports files on disk: {len(disk_reports)}, referenced in DB: {len(db_report_images)}")
    print(f"Total evidence files on disk: {len(disk_evidence)}, referenced in DB: {len(db_evidence_files)}")
    print(f"Orphan report uploads identified: {len(orphan_reports)}")
    print(f"Orphan evidence uploads identified: {len(orphan_evidence)}")

    if not dry_run:
        purged = 0
        for f in orphan_reports:
            p = reports_dir / f
            if p.is_file():
                p.unlink()
                purged += 1
        for f in orphan_evidence:
            p = evidence_dir / f
            if p.is_file():
                p.unlink()
                purged += 1
        print(f"Successfully purged {purged} orphan upload files.")
    else:
        print("[DRY RUN] No files deleted. Pass dry_run=False to execute purge.")

if __name__ == "__main__":
    audit_and_clean_orphan_uploads(dry_run=True)
