"""CivicSight Priority and Proximity Backfill Script (Week 8)

Computes severity, priority, priority_score, priority_reasons, nearby_report_count,
and report_relations for all existing reports in the database without destroying data.
"""

import os
import sys
import time

# Ensure backend root is on sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.db.database import SessionLocal
from app.db.init_db import init_db
from app.models.models import Report
from app.services.proximity import process_report_proximity, update_single_report_priority


def run_backfill():
    print("=" * 70)
    print("CIVICSIGHT WEEK 8: PRIORITY & PROXIMITY BACKFILL SCRIPT")
    print("=" * 70)

    # Ensure schema updates and tables exist
    init_db()

    db = SessionLocal()
    start_time = time.time()
    try:
        reports = db.query(Report).order_by(Report.id.asc()).all()
        total_reports = len(reports)
        print(f"[*] Found {total_reports} existing report(s) to process.")

        priority_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "UNKNOWN": 0, "NULL": 0}
        relations_created = 0

        for idx, report in enumerate(reports, 1):
            # Process spatial proximity & create relations
            rels = process_report_proximity(report, db, recalculate_neighbors=False)
            relations_created += len(rels)

            # Compute priority, severity, score, reasons
            res = update_single_report_priority(report, db, trigger="backfill")

            p_val = report.priority or "NULL"
            priority_counts[p_val] = priority_counts.get(p_val, 0) + 1

            print(
                f"[{idx:03d}/{total_reports:03d}] Report #{report.id}: "
                f"Severity={report.severity} | Priority={report.priority} | "
                f"Score={report.priority_score:.1f} | Nearby={report.nearby_report_count} | "
                f"Reasons={len(report.priority_reasons or [])}"
            )

        db.commit()
        duration = time.time() - start_time

        print("\n" + "=" * 70)
        print("BACKFILL COMPLETED SUCCESSFULLY")
        print(f"Total processed: {total_reports}")
        print(f"Time taken: {duration:.2f} seconds")
        print(f"Priority distribution: {priority_counts}")
        print("=" * 70)

    except Exception as e:
        db.rollback()
        print(f"[!] Error during backfill: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_backfill()
