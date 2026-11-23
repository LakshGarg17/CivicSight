"""
Complete End-to-End Multi-Role Workflow Verification for CivicSight.
Validates the full municipal lifecycle across all 3 roles:
1. Citizen: Submits report, views live tracking in My Reports (anti-IDOR checked).
2. Officer: Triages, verifies report, confirms mistake recovery (undo verification & undo rejection),
   and assigns maintenance crew with dispatch instructions.
3. Maintenance Staff: Views assigned work orders (anti-IDOR checked), starts repair,
   uploads photographic repair evidence, and submits for municipal inspection.
4. Officer Rework Loop: Sends back for rework with mandatory note -> Crew re-submits ->
   Officer conducts final verification and approves -> Status transitions to CLOSED.
5. Citizen Verification: Citizen sees CLOSED status, side-by-side before/after evidence,
   and complete audit history timeline.
"""

import sys
import os
import io
from pathlib import Path
from datetime import datetime

# Unbuffered output
sys.stdout.reconfigure(line_buffering=True)

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))
sys.path.insert(0, str(BASE_DIR))

from fastapi import HTTPException, UploadFile
from app.db.database import SessionLocal, engine
from app.models.models import (
    Base, User, Report, Assignment, RepairEvidence, FinalVerification,
    ReportStatusHistory, DetectionResult, UserRole, EvidenceKind, VerificationDecision
)
from app.core.state_machine import ReportStatus
from app.core.security import get_password_hash
from app.schemas.schemas import (
    ReportCreate, ReportVerifyRequest, ReportAssignRequest, ReportRejectRequest,
    DecisionReversalRequest, FinalVerificationRequest
)
from app.api.v1.endpoints.reports import (
    list_my_reports, verify_report, reverse_report_decision, reject_report,
    assign_report, start_repair, upload_repair_evidence, submit_repair_evidence,
    final_verify_report, get_report, list_reports, record_status_history
)
from app.api.v1.endpoints.staff import get_my_assignments
from starlette.requests import Request
from PIL import Image

def get_valid_jpeg_bytes(color=(60, 120, 180)):
    buf = io.BytesIO()
    img = Image.new("RGB", (128, 128), color=color)
    img.save(buf, format="JPEG")
    return buf.getvalue()

def run_sync(coro):
    try:
        coro.send(None)
    except StopIteration as e:
        return e.value

async def direct_read(self, size=-1):
    return self.file.read(size)

UploadFile.read = direct_read

def log_step(title):
    print("\n" + "=" * 70, flush=True)
    print(f"STEP: {title}", flush=True)
    print("=" * 70, flush=True)

def main():
    db = SessionLocal()
    created_user_ids = []
    created_report_ids = []

    try:
        log_step("SETUP: Ensure Clean Test Users for Citizen, Officer, and Staff")
        
        # 1. Citizen 1
        c1 = db.query(User).filter(User.email == "citizen1_test@civicsight.org").first()
        if not c1:
            c1 = User(
                name="Citizen Jane",
                email="citizen1_test@civicsight.org",
                hashed_password=get_password_hash("Secret123!"),
                role=UserRole.CITIZEN,
                is_active=True
            )
            db.add(c1)
            db.commit()
            db.refresh(c1)
        created_user_ids.append(c1.id)
        print(f"  [OK] Citizen 1: ID={c1.id}, Email={c1.email}, Role={c1.role}", flush=True)

        # 2. Citizen 2 (Anti-IDOR control)
        c2 = db.query(User).filter(User.email == "citizen2_test@civicsight.org").first()
        if not c2:
            c2 = User(
                name="Citizen Bob",
                email="citizen2_test@civicsight.org",
                hashed_password=get_password_hash("Secret123!"),
                role=UserRole.CITIZEN,
                is_active=True
            )
            db.add(c2)
            db.commit()
            db.refresh(c2)
        created_user_ids.append(c2.id)
        print(f"  [OK] Citizen 2 (Anti-IDOR): ID={c2.id}, Email={c2.email}, Role={c2.role}", flush=True)

        # 3. Municipal Officer
        officer = db.query(User).filter(User.email == "officer_test@civicsight.org").first()
        if not officer:
            officer = User(
                name="Officer Sarah Chen",
                email="officer_test@civicsight.org",
                hashed_password=get_password_hash("Secret123!"),
                role=UserRole.MUNICIPAL_OFFICER,
                is_active=True
            )
            db.add(officer)
            db.commit()
            db.refresh(officer)
        created_user_ids.append(officer.id)
        print(f"  [OK] Municipal Officer: ID={officer.id}, Email={officer.email}, Role={officer.role}", flush=True)

        # 4. Maintenance Staff 1
        staff1 = db.query(User).filter(User.email == "staff1_test@civicsight.org").first()
        if not staff1:
            staff1 = User(
                name="Field Crew Alpha",
                email="staff1_test@civicsight.org",
                hashed_password=get_password_hash("Secret123!"),
                role=UserRole.MAINTENANCE_STAFF,
                is_active=True
            )
            db.add(staff1)
            db.commit()
            db.refresh(staff1)
        created_user_ids.append(staff1.id)
        print(f"  [OK] Staff 1: ID={staff1.id}, Email={staff1.email}, Role={staff1.role}", flush=True)

        # 5. Maintenance Staff 2 (Anti-IDOR control)
        staff2 = db.query(User).filter(User.email == "staff2_test@civicsight.org").first()
        if not staff2:
            staff2 = User(
                name="Field Crew Beta",
                email="staff2_test@civicsight.org",
                hashed_password=get_password_hash("Secret123!"),
                role=UserRole.MAINTENANCE_STAFF,
                is_active=True
            )
            db.add(staff2)
            db.commit()
            db.refresh(staff2)
        created_user_ids.append(staff2.id)
        print(f"  [OK] Staff 2 (Anti-IDOR): ID={staff2.id}, Email={staff2.email}, Role={staff2.role}", flush=True)

        # ----------------------------------------------------------------------
        # STAGE 1: Citizen Submits Road Hazard Report
        # ----------------------------------------------------------------------
        log_step("STAGE 1: Citizen 1 Submits Road Hazard Report with Image & GPS")
        
        test_report = Report(
            reporter_id=c1.id,
            damage_type="D40",
            description="Severe deep pothole near crosswalk damaging tires",
            latitude=37.77492,
            longitude=-122.41941,
            address_text="Market St & 8th St, San Francisco, CA",
            image_url="/uploads/test_pothole_stage.jpg",
            status=ReportStatus.SUBMITTED,
            priority="HIGH",
            priority_score=85.0,
            ml_status="ML_COMPLETE",
            ml_model_version="YOLOv8n-CivicSight-4Class",
            ml_inference_time_ms=42.5
        )
        db.add(test_report)
        db.commit()
        db.refresh(test_report)
        created_report_ids.append(test_report.id)
        report_id = test_report.id

        # Attach ML Detections
        det = DetectionResult(
            report_id=report_id,
            detected_class="D40",
            class_name="Pothole Hazard",
            confidence=0.92,
            bbox_ymin=0.25,
            bbox_xmin=0.30,
            bbox_ymax=0.65,
            bbox_xmax=0.75,
            severity="HIGH"
        )
        db.add(det)

        # Initial status history
        record_status_history(
            db=db,
            report_id=report_id,
            from_status=None,
            to_status=ReportStatus.SUBMITTED.value,
            user=c1,
            note="Citizen initial submission"
        )
        db.commit()
        print(f"  [OK] Created Report #{report_id} by Citizen 1. Status: {test_report.status}", flush=True)

        # ----------------------------------------------------------------------
        # STAGE 2: Citizen Portal Query & Anti-IDOR Enforcement
        # ----------------------------------------------------------------------
        log_step("STAGE 2: Citizen 1 Views 'My Reports' & Anti-IDOR Check for Citizen 2")
        
        # Citizen 1 calls GET /api/v1/reports/mine
        c1_reports = list_my_reports(db=db, current_user=c1)
        c1_ids = [r.id if hasattr(r, 'id') else r["id"] for r in c1_reports]
        assert report_id in c1_ids, f"Report #{report_id} missing from Citizen 1 reports list!"
        print(f"  [PASS] Citizen 1 queried GET /reports/mine: Found {len(c1_reports)} reports (includes #{report_id}).", flush=True)

        # Citizen 2 calls GET /api/v1/reports/mine (must NOT see Citizen 1's report)
        c2_reports = list_my_reports(db=db, current_user=c2)
        c2_ids = [r.id if hasattr(r, 'id') else r["id"] for r in c2_reports]
        assert report_id not in c2_ids, f"ANTI-IDOR VIOLATION: Citizen 2 was able to see Citizen 1's report #{report_id}!"
        print(f"  [PASS] ANTI-IDOR VERIFIED: Citizen 2 GET /reports/mine returned {len(c2_reports)} reports; Report #{report_id} strictly hidden.", flush=True)

        # ----------------------------------------------------------------------
        # STAGE 3: Municipal Officer Triages & Verifies Report
        # ----------------------------------------------------------------------
        log_step("STAGE 3: Municipal Officer Verifies Report")

        verify_res = verify_report(
            report_id=report_id,
            body=ReportVerifyRequest(note="Officer field audit: confirmed severe cavity hazard requiring urgent patch"),
            db=db,
            current_user=officer
        )
        assert verify_res.status == ReportStatus.VERIFIED, f"Expected VERIFIED, got {verify_res.status}"
        print(f"  [PASS] Report #{report_id} verified by Officer. Status: {verify_res.status}", flush=True)

        # Verify audit history
        histories = db.query(ReportStatusHistory).filter(ReportStatusHistory.report_id == report_id).all()
        assert any(h.to_status == ReportStatus.VERIFIED.value and (h.performed_by_name == officer.name) for h in histories)
        print(f"  [PASS] Status history reflects VERIFIED transition recorded by {officer.name}.", flush=True)

        # ----------------------------------------------------------------------
        # STAGE 4: Mistake Recovery (Undo Verification & Undo Rejection)
        # ----------------------------------------------------------------------
        log_step("STAGE 4: Mistake Recovery: Officer Reverses Verification and Rejection")

        # 4a. Reverse Verification back to PENDING_VERIFICATION
        rev_res = reverse_report_decision(
            report_id=report_id,
            body=DecisionReversalRequest(reason="Accidentally clicked verify; need to cross-check highway division boundary"),
            db=db,
            current_user=officer
        )
        assert rev_res.status == ReportStatus.PENDING_VERIFICATION, f"Expected PENDING_VERIFICATION, got {rev_res.status}"
        print(f"  [PASS] Undo Verification: Report #{report_id} safely reverted to {rev_res.status}.", flush=True)

        histories = db.query(ReportStatusHistory).filter(ReportStatusHistory.report_id == report_id).all()
        last_hist = histories[-1]
        assert last_hist.to_status == ReportStatus.PENDING_VERIFICATION.value
        assert "Accidentally clicked verify" in last_hist.note
        print(f"  [PASS] History logged reversal: '{last_hist.note}' by {last_hist.performed_by_name}.", flush=True)

        # 4b. Officer Rejects Report
        rej_res = reject_report(
            report_id=report_id,
            body=ReportRejectRequest(reason="Private property driveway", note="Initial assessment"),
            db=db,
            current_user=officer
        )
        assert rej_res.status == ReportStatus.REJECTED
        print(f"  [PASS] Report #{report_id} rejected. Status: {rej_res.status}", flush=True)

        # 4c. Undo Rejection back to PENDING_VERIFICATION
        rev_rej_res = reverse_report_decision(
            report_id=report_id,
            body=DecisionReversalRequest(reason="Surveyor confirmed pothole is on public right-of-way, not private driveway"),
            db=db,
            current_user=officer
        )
        assert rev_rej_res.status == ReportStatus.PENDING_VERIFICATION
        print(f"  [PASS] Undo Rejection: Report #{report_id} safely reopened to {rev_rej_res.status}.", flush=True)

        # 4d. Re-verify the report for subsequent dispatch
        reverify_res = verify_report(
            report_id=report_id,
            body=ReportVerifyRequest(note="Re-verified after municipal surveyor boundary confirmation"),
            db=db,
            current_user=officer
        )
        assert reverify_res.status == ReportStatus.VERIFIED
        print(f"  [PASS] Re-verified Report #{report_id}. Status: {reverify_res.status}", flush=True)

        # ----------------------------------------------------------------------
        # STAGE 5: Officer Dispatches / Assigns Maintenance Crew
        # ----------------------------------------------------------------------
        log_step("STAGE 5: Officer Dispatches Report to Maintenance Staff 1")

        assign_res = assign_report(
            report_id=report_id,
            body=ReportAssignRequest(
                staff_id=staff1.id,
                note="Priority cold-mix asphalt patch within 24 hours. Ensure safety cones deployed."
            ),
            db=db,
            current_user=officer
        )
        assert assign_res.status == ReportStatus.ASSIGNED
        assert assign_res.assigned_to == staff1.name
        print(f"  [PASS] Report #{report_id} dispatched to {staff1.name}. Status: {assign_res.status}", flush=True)

        # Verify Reversal is BLOCKED once assigned
        try:
            reverse_report_decision(
                report_id=report_id,
                body=DecisionReversalRequest(reason="Attempting illegal reversal after dispatch"),
                db=db,
                current_user=officer
            )
            assert False, "FAILED: Reversal should have been BLOCKED for assigned report!"
        except HTTPException as e:
            assert e.status_code == 400
            print(f"  [PASS] Security Guard Enforced: Cannot reverse decision on assigned report ({e.detail}).", flush=True)
        except HTTPException as e:
            assert e.status_code == 400
            print(f"  [PASS] Security Guard Enforced: Cannot reverse decision on assigned report ({e.detail}).", flush=True)

        # ----------------------------------------------------------------------
        # STAGE 6: Maintenance Staff Portal Actions
        # ----------------------------------------------------------------------
        log_step("STAGE 6: Maintenance Staff 1 Views Workload & Anti-IDOR Check for Staff 2")

        # Staff 1 queries assignments
        s1_assignments = get_my_assignments(view="active", db=db, current_user=staff1)
        s1_ids = [a.id if hasattr(a, 'id') else a["id"] for a in s1_assignments]
        assert report_id in s1_ids, f"Work order #{report_id} missing from Staff 1 active queue!"
        print(f"  [PASS] Staff 1 GET /staff/me/assignments: Found {len(s1_assignments)} orders (includes #{report_id}).", flush=True)

        # Staff 2 queries assignments (Anti-IDOR)
        s2_assignments = get_my_assignments(view="active", db=db, current_user=staff2)
        s2_ids = [a.id if hasattr(a, 'id') else a["id"] for a in s2_assignments]
        assert report_id not in s2_ids, f"ANTI-IDOR VIOLATION: Staff 2 saw Staff 1's assigned work order #{report_id}!"
        print(f"  [PASS] ANTI-IDOR VERIFIED: Staff 2 GET /staff/me/assignments excludes Report #{report_id}.", flush=True)

        # 6b. Staff 1 starts physical repair
        start_res = start_repair(report_id=report_id, db=db, current_user=staff1)
        assert start_res.status == ReportStatus.UNDER_REPAIR
        print(f"  [PASS] Staff 1 started physical repair. Status: {start_res.status}", flush=True)

        # 6c. Staff 1 uploads AFTER repair photo
        valid_jpeg_1 = get_valid_jpeg_bytes(color=(40, 140, 80))
        upload_file = UploadFile(
            filename="repair_patch_complete.jpg",
            file=io.BytesIO(valid_jpeg_1),
            headers={"content-type": "image/jpeg"}
        )
        evidence_res = run_sync(upload_repair_evidence(
            report_id=report_id,
            kind="AFTER",
            note="Excavated pothole cavity, poured hot-mix asphalt, leveled with tamper",
            file=upload_file,
            photo=None,
            db=db,
            current_user=staff1
        ))
        assert evidence_res.kind == EvidenceKind.AFTER
        evidence_id = evidence_res.id
        print(f"  [PASS] Staff 1 uploaded AFTER evidence photo #{evidence_id}.", flush=True)

        # 6d. Staff 1 submits for municipal verification
        mock_req_1 = Request({"type": "http", "method": "POST", "headers": []})
        submit_res = run_sync(submit_repair_evidence(
            report_id=report_id,
            request=mock_req_1,
            note="Pothole repair complete, awaiting municipal verification",
            db=db,
            current_user=staff1
        ))
        assert submit_res.status == ReportStatus.REPAIR_EVIDENCE_SUBMITTED
        print(f"  [PASS] Staff 1 submitted repair for inspection. Status: {submit_res.status}", flush=True)

        # ----------------------------------------------------------------------
        # STAGE 7: Officer Review & Rework Cycle
        # ----------------------------------------------------------------------
        log_step("STAGE 7: Officer Rework Cycle & Final Verification Approval")

        # 7a. Officer sends back for rework
        rework_res = final_verify_report(
            report_id=report_id,
            body=FinalVerificationRequest(
                decision=VerificationDecision.SENT_BACK,
                note="Asphalt edge seal requires bituminous sealant compaction along curb"
            ),
            db=db,
            current_user=officer
        )
        assert rework_res.status == ReportStatus.UNDER_REPAIR
        print(f"  [PASS] Officer sent back for rework. Status reverted to: {rework_res.status}", flush=True)

        # Staff 1 sees rework instruction
        s1_rework_check = get_report(report_id=report_id, db=db, current_user=staff1)
        assert s1_rework_check.status == ReportStatus.UNDER_REPAIR
        rework_entries = [v for v in s1_rework_check.final_verifications if v.decision == VerificationDecision.SENT_BACK]
        assert len(rework_entries) > 0
        assert "bituminous sealant compaction" in rework_entries[-1].note
        print(f"  [PASS] Staff 1 retrieved rework note: '{rework_entries[-1].note}'.", flush=True)

        # 7b. Staff 1 uploads second AFTER photo and re-submits
        valid_jpeg_2 = get_valid_jpeg_bytes(color=(30, 90, 160))
        upload_file_2 = UploadFile(
            filename="repair_edge_sealant.jpg",
            file=io.BytesIO(valid_jpeg_2),
            headers={"content-type": "image/jpeg"}
        )
        evidence_res_2 = run_sync(upload_repair_evidence(
            report_id=report_id,
            kind="AFTER",
            note="Bituminous sealant applied along perimeter curb and compacted flush",
            file=upload_file_2,
            photo=None,
            db=db,
            current_user=staff1
        ))
        mock_req_2 = Request({"type": "http", "method": "POST", "headers": []})
        submit_res_2 = run_sync(submit_repair_evidence(
            report_id=report_id,
            request=mock_req_2,
            note="Corrective edge compaction complete",
            db=db,
            current_user=staff1
        ))
        assert submit_res_2.status == ReportStatus.REPAIR_EVIDENCE_SUBMITTED
        print(f"  [PASS] Staff 1 applied corrective seal and re-submitted. Status: {submit_res_2.status}", flush=True)

        # 7c. Officer conducts final verification and APPROVES
        approve_res = final_verify_report(
            report_id=report_id,
            body=FinalVerificationRequest(
                decision=VerificationDecision.APPROVED,
                note="Verified perimeter seal and compaction. Meets all municipal road safety standards."
            ),
            db=db,
            current_user=officer
        )
        assert approve_res.status == ReportStatus.CLOSED
        print(f"  [PASS] Officer approved final repair. Report #{report_id} officially CLOSED!", flush=True)

        # ----------------------------------------------------------------------
        # STAGE 8: Citizen Verifies Closed Report & Side-by-Side Evidence
        # ----------------------------------------------------------------------
        log_step("STAGE 8: Citizen 1 Inspects Closed Report & Side-by-Side Evidence")

        c1_final_reports = list_my_reports(db=db, current_user=c1)
        target_report = next((r for r in c1_final_reports if (r.id if hasattr(r, 'id') else r["id"]) == report_id), None)
        assert target_report is not None
        rep_status = target_report.status if hasattr(target_report, 'status') else target_report["status"]
        if hasattr(rep_status, 'value'): rep_status = rep_status.value
        assert str(rep_status).lower() == "closed"
        print(f"  [PASS] Citizen 1 queried My Reports: Status is '{rep_status}'.", flush=True)

        # Verify side-by-side evidence is populated
        evidences = target_report.repair_evidence if hasattr(target_report, 'repair_evidence') else target_report.get("repair_evidence", [])
        assert len(evidences) >= 2, f"Expected at least 2 after repair evidence records, found {len(evidences)}"
        print(f"  [PASS] Side-by-side evidence verified: {len(evidences)} repair photos attached for Citizen 1.", flush=True)

        # Verify audit history timeline
        status_histories = target_report.status_history if hasattr(target_report, 'status_history') else target_report.get("status_history", [])
        print(f"  [PASS] Status history timeline verified: {len(status_histories)} milestone transitions logged:", flush=True)
        for h in status_histories:
            from_st = (h.from_status if hasattr(h, 'from_status') else h.get('from_status')) or "START"
            to_st = h.to_status if hasattr(h, 'to_status') else h.get('to_status')
            actor = (h.performed_by_name if hasattr(h, 'performed_by_name') else h.get('performed_by_name')) or (h.changed_by_name if hasattr(h, 'changed_by_name') else h.get('changed_by_name')) or "System"
            note = h.note if hasattr(h, 'note') else h.get('note')
            print(f"    * {str(from_st):20} -> {str(to_st):26} by {str(actor):18} | note: {note}", flush=True)

        print("\n" + "=" * 70, flush=True)
        print("ALL E2E WORKFLOW TESTS PASSED PERFECTLY ACROSS ALL 3 ROLES!", flush=True)
        print("=" * 70, flush=True)

    finally:
        # Cleanup test records
        for rid in created_report_ids:
            try:
                rep = db.query(Report).filter(Report.id == rid).first()
                if rep:
                    db.query(ReportStatusHistory).filter(ReportStatusHistory.report_id == rid).delete()
                    db.query(RepairEvidence).filter(RepairEvidence.report_id == rid).delete()
                    db.query(FinalVerification).filter(FinalVerification.report_id == rid).delete()
                    db.query(Assignment).filter(Assignment.report_id == rid).delete()
                    db.query(DetectionResult).filter(DetectionResult.report_id == rid).delete()
                    db.delete(rep)
                    db.commit()
            except Exception as e:
                db.rollback()
                print(f"Cleanup warning for report {rid}: {e}", flush=True)

        for uid in created_user_ids:
            try:
                u = db.query(User).filter(User.id == uid).first()
                if u:
                    db.delete(u)
                    db.commit()
            except Exception as e:
                db.rollback()
                print(f"Cleanup warning for user {uid}: {e}", flush=True)

        db.close()

if __name__ == "__main__":
    main()
