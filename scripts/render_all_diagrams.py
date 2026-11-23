"""
CivicSight Phase 6 Diagram Renderer
Renders every architectural diagram to SVG and PNG in /docs/diagrams/rendered/.
Uses Playwright to capture pixel-perfect PNGs from SVGs.
"""

import os
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = BASE_DIR / "docs" / "diagrams" / "src"
RENDERED_DIR = BASE_DIR / "docs" / "diagrams" / "rendered"
RENDERED_DIR.mkdir(parents=True, exist_ok=True)

# Define SVG generation templates for each diagram
# Clean, modern vector styling with readable typography and high contrast
def make_svg(title, subtitle, boxes, arrows, width=1200, height=800):
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">
  <defs>
    <style>
      .title {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 24px; font-weight: bold; fill: #111827; }}
      .subtitle {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 14px; fill: #4b5563; }}
      .box-bg {{ fill: #ffffff; stroke: #1f2937; stroke-width: 2px; rx: 8px; }}
      .box-bg-highlight {{ fill: #f3f4f6; stroke: #111827; stroke-width: 2.5px; rx: 8px; }}
      .box-bg-actor {{ fill: #000000; stroke: #000000; stroke-width: 2px; rx: 8px; }}
      .box-title {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 15px; font-weight: 600; fill: #111827; }}
      .box-text {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 13px; fill: #374151; }}
      .actor-text {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 15px; font-weight: bold; fill: #ffffff; }}
      .arrow {{ stroke: #1f2937; stroke-width: 2px; fill: none; }}
      .arrow-label {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 12px; fill: #4b5563; text-anchor: middle; }}
    </style>
    <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
      <polygon points="0 0, 10 3.5, 0 7" fill="#1f2937" />
    </marker>
  </defs>
  <rect width="{width}" height="{height}" fill="#f9fafb" />
  <text x="40" y="50" class="title">{title}</text>
  <text x="40" y="75" class="subtitle">{subtitle}</text>
'''
    # Add elements
    for b in boxes:
        cls = b.get("cls", "box-bg")
        tcls = "actor-text" if "actor" in cls else "box-title"
        svg += f'  <g transform="translate({b["x"]}, {b["y"]})">\n'
        svg += f'    <rect width="{b["w"]}" height="{b["h"]}" class="{cls}" />\n'
        svg += f'    <text x="{b["w"]/2}" y="28" text-anchor="middle" class="{tcls}">{b["title"]}</text>\n'
        if "lines" in b:
            for l_idx, line in enumerate(b["lines"]):
                svg += f'    <text x="15" y="{52 + l_idx*20}" class="box-text">{line}</text>\n'
        svg += '  </g>\n'

    for a in arrows:
        svg += f'  <line x1="{a["x1"]}" y1="{a["y1"]}" x2="{a["x2"]}" y2="{a["y2"]}" class="arrow" marker-end="url(#arrowhead)" />\n'
        if "label" in a:
            mx = (a["x1"] + a["x2"]) / 2
            my = (a["y1"] + a["y2"]) / 2 - 6
            svg += f'  <text x="{mx}" y="{my}" class="arrow-label">{a["label"]}</text>\n'

    svg += '</svg>'
    return svg

# Render all 15 diagrams
diagram_specs = [
    {
        "name": "use_case_diagram",
        "title": "CivicSight — Use Case Diagram",
        "subtitle": "System actors, user capabilities, and external services",
        "boxes": [
            {"x": 60, "y": 140, "w": 180, "h": 60, "title": "Citizen", "cls": "box-bg-actor"},
            {"x": 60, "y": 300, "w": 180, "h": 60, "title": "Municipal Officer", "cls": "box-bg-actor"},
            {"x": 60, "y": 480, "w": 180, "h": 60, "title": "Maintenance Staff", "cls": "box-bg-actor"},
            {"x": 60, "y": 640, "w": 180, "h": 60, "title": "Administrator", "cls": "box-bg-actor"},
            {"x": 380, "y": 120, "w": 340, "h": 100, "title": "Report Submission & Tracking", "lines": ["• Geolocation & Pinpoint", "• My Reports Live Timeline"]},
            {"x": 380, "y": 270, "w": 340, "h": 150, "title": "Triage & Review Center", "lines": ["• Verify / Reject Reports", "• Revert Mistake Decisions", "• Dispatch Work Orders to Crew"]},
            {"x": 380, "y": 460, "w": 340, "h": 140, "title": "Field Repair & Evidence", "lines": ["• Start Work (UNDER_REPAIR)", "• Upload Before/After Photos", "• Submit for Municipal Sign-off"]},
            {"x": 380, "y": 630, "w": 340, "h": 100, "title": "Audit & User Governance", "lines": ["• RBAC Account Allocation", "• Emergency Reopen & Logs"]},
            {"x": 860, "y": 200, "w": 280, "h": 120, "title": "External: YOLOv8s ML", "lines": ["• RDD2022 Defect Detection", "• Bounding Box & Conf.", "• 4 Defect Classes (D00-D40)"], "cls": "box-bg-highlight"},
            {"x": 860, "y": 380, "w": 280, "h": 120, "title": "External: Google Maps API", "lines": ["• Dynamic JS API Loader", "• Geocoding & Manual Pin", "• Zero Key Leakage Guard"], "cls": "box-bg-highlight"},
        ],
        "arrows": [
            {"x1": 240, "y1": 170, "x2": 380, "y2": 170, "label": "Submits & Tracks"},
            {"x1": 240, "y1": 330, "x2": 380, "y2": 330, "label": "Triages & Dispatches"},
            {"x1": 240, "y1": 510, "x2": 380, "y2": 510, "label": "Remediates & Uploads"},
            {"x1": 240, "y1": 670, "x2": 380, "y2": 670, "label": "Administers"},
            {"x1": 720, "y1": 170, "x2": 860, "y2": 240, "label": "Inference"},
            {"x1": 720, "y1": 200, "x2": 860, "y2": 420, "label": "Maps & Pin"},
        ]
    },
    {
        "name": "state_diagram",
        "title": "CivicSight — Canonical Lifecycle State Machine",
        "subtitle": "Complete report lifecycle states and legal transition graph",
        "boxes": [
            {"x": 60, "y": 350, "w": 180, "h": 70, "title": "SUBMITTED", "lines": ["Fresh Citizen Report"]},
            {"x": 300, "y": 200, "w": 220, "h": 70, "title": "PENDING_VERIFICATION", "lines": ["Municipal Triage Queue"]},
            {"x": 600, "y": 200, "w": 180, "h": 70, "title": "VERIFIED", "lines": ["Hazard Validated"]},
            {"x": 860, "y": 200, "w": 180, "h": 70, "title": "ASSIGNED", "lines": ["Dispatched to Crew"]},
            {"x": 860, "y": 380, "w": 200, "h": 70, "title": "UNDER_REPAIR", "lines": ["Crew Active On Site"]},
            {"x": 520, "y": 380, "w": 260, "h": 70, "title": "REPAIR_EVIDENCE_SUBMITTED", "lines": ["Photos Uploaded for Review"]},
            {"x": 200, "y": 380, "w": 180, "h": 70, "title": "CLOSED", "lines": ["Final Inspection APPROVED"], "cls": "box-bg-highlight"},
            {"x": 300, "y": 550, "w": 200, "h": 70, "title": "REJECTED", "lines": ["Discarded with Reason"], "cls": "box-bg-highlight"},
        ],
        "arrows": [
            {"x1": 240, "y1": 370, "x2": 300, "y2": 240, "label": "Enrich"},
            {"x1": 520, "y1": 235, "x2": 600, "y2": 235, "label": "Verify"},
            {"x1": 780, "y1": 235, "x2": 860, "y2": 235, "label": "Assign"},
            {"x1": 950, "y1": 270, "x2": 950, "y2": 380, "label": "Start Work"},
            {"x1": 860, "y1": 415, "x2": 780, "y2": 415, "label": "Upload Evidence"},
            {"x1": 520, "y1": 415, "x2": 380, "y2": 415, "label": "Approve"},
            {"x1": 650, "y1": 450, "x2": 860, "y2": 430, "label": "Send Back (Rework)"},
            {"x1": 400, "y1": 270, "x2": 400, "y2": 550, "label": "Reject"},
            {"x1": 450, "y1": 550, "x2": 450, "y2": 270, "label": "Mistake Recovery"},
        ]
    },
    {
        "name": "er_diagram",
        "title": "CivicSight — Relational Entity-Relationship Diagram",
        "subtitle": "9 relational tables with primary keys, foreign keys, and cardinalities",
        "boxes": [
            {"x": 60, "y": 140, "w": 280, "h": 220, "title": "users", "lines": ["• id: INTEGER (PK)", "• name: VARCHAR(120)", "• email: VARCHAR(255) (UK)", "• role: VARCHAR(50)", "• is_active: BOOLEAN", "• hashed_password", "• created_at, updated_at"]},
            {"x": 440, "y": 140, "w": 340, "h": 260, "title": "reports", "lines": ["• id: INTEGER (PK)", "• reporter_id: INTEGER (FK)", "• status: VARCHAR(50)", "• priority: VARCHAR(20)", "• priority_score: FLOAT", "• damage_type: VARCHAR(50)", "• ml_status: VARCHAR(50)", "• latitude, longitude", "• image_url: VARCHAR(500)", "• created_at, updated_at"]},
            {"x": 880, "y": 140, "w": 280, "h": 180, "title": "detection_results", "lines": ["• id: INTEGER (PK)", "• report_id: INTEGER (FK)", "• detected_class: VARCHAR(50)", "• confidence: FLOAT", "• bbox_xmin, ymin, xmax, ymax", "• severity: VARCHAR(20)"]},
            {"x": 60, "y": 440, "w": 300, "h": 180, "title": "assignments", "lines": ["• id: INTEGER (PK)", "• report_id: INTEGER (FK)", "• assigned_to: INTEGER (FK)", "• assigned_by: INTEGER (FK)", "• is_active: BOOLEAN", "• assigned_at, unassigned_at"]},
            {"x": 440, "y": 460, "w": 340, "h": 190, "title": "repair_evidence", "lines": ["• id: INTEGER (PK)", "• report_id: INTEGER (FK)", "• uploaded_by: INTEGER (FK)", "• kind: BEFORE / AFTER / PROGRESS", "• file_path, checksum (SHA-256)", "• uploaded_at: DATETIME"]},
            {"x": 880, "y": 420, "w": 280, "h": 160, "title": "final_verifications", "lines": ["• id: INTEGER (PK)", "• report_id: INTEGER (FK)", "• officer_id: INTEGER (FK)", "• decision: APPROVED / SENT_BACK", "• note: TEXT", "• created_at: DATETIME"]},
        ],
        "arrows": [
            {"x1": 340, "y1": 200, "x2": 440, "y2": 200, "label": "1:N submits"},
            {"x1": 780, "y1": 200, "x2": 880, "y2": 200, "label": "1:N contains"},
            {"x1": 500, "y1": 400, "x2": 360, "y2": 480, "label": "1:N work orders"},
            {"x1": 600, "y1": 400, "x2": 600, "y2": 460, "label": "1:N evidence"},
            {"x1": 720, "y1": 400, "x2": 880, "y2": 480, "label": "1:N inspections"},
        ]
    },
    {
        "name": "class_diagram",
        "title": "CivicSight — Domain Class & Architecture Diagram",
        "subtitle": "SQLAlchemy models, Pydantic schemas, and core system services",
        "boxes": [
            {"x": 60, "y": 140, "w": 300, "h": 180, "title": "Report (Model)", "lines": ["+id: int", "+reporter_id: int", "+status: ReportStatus", "+priority: str", "+damage_type: str", "+latitude, longitude: float"]},
            {"x": 420, "y": 140, "w": 340, "h": 180, "title": "PriorityConfig (Service)", "lines": ["+class_weights: dict", "+min_confidence: float = 0.25", "+high_priority_score_threshold: 60.0", "+from_env() -> PriorityConfig", "+calculate_priority() -> dict"]},
            {"x": 820, "y": 140, "w": 320, "h": 180, "title": "MLService (Adapter)", "lines": ["+model: YOLOv8s", "+weights: best.pt (RDD2022)", "+run_ml_inference_guarded()", "+process_report_image_ml()"]},
            {"x": 60, "y": 420, "w": 300, "h": 180, "title": "User (Model)", "lines": ["+id: int", "+email: str", "+name: str", "+role: UserRole", "+hashed_password: str", "+is_active: bool"]},
            {"x": 420, "y": 420, "w": 340, "h": 180, "title": "StateMachine (Core)", "lines": ["+CANONICAL_STATUSES: set", "+LEGAL_TRANSITIONS: dict", "+ROLE_TRANSITIONS: dict", "+validate_transition()"]},
            {"x": 820, "y": 420, "w": 320, "h": 180, "title": "ProximityService (Service)", "lines": ["+haversine_distance()", "+get_bounding_box()", "+process_report_proximity()"]},
        ],
        "arrows": [
            {"x1": 360, "y1": 200, "x2": 420, "y2": 200, "label": "Scores"},
            {"x1": 760, "y1": 200, "x2": 820, "y2": 200, "label": "Feeds Defect Class"},
            {"x1": 210, "y1": 320, "x2": 210, "y2": 420, "label": "Authored By"},
            {"x1": 360, "y1": 480, "x2": 420, "y2": 480, "label": "Enforces RBAC"},
            {"x1": 600, "y1": 320, "x2": 820, "y2": 450, "label": "Clustering Density"},
        ]
    },
    {
        "name": "deployment_diagram",
        "title": "CivicSight — System Deployment View",
        "subtitle": "Client tiers, FastAPI application node, ML process, and persistent storage",
        "boxes": [
            {"x": 60, "y": 140, "w": 280, "h": 160, "title": "Citizen & Crew Devices", "lines": ["• Mobile Safari / Chrome", "• HTML5 Geolocation", "• Offline Manual Fallback", "• Responsive 360px - 1440px"], "cls": "box-bg-highlight"},
            {"x": 60, "y": 400, "w": 280, "h": 160, "title": "Municipal Workstations", "lines": ["• Desktop Chromium / Firefox", "• High-Contrast Theme System", "• Real-Time Triage Dashboard", "• 1024px - 1920px Resolution"], "cls": "box-bg-highlight"},
            {"x": 440, "y": 200, "w": 360, "h": 320, "title": "Application Host Node", "lines": [
                "• Uvicorn ASGI Server (:8000)",
                "• FastAPI REST Framework",
                "• JWT HS256 Token Auth",
                "• Canonical State Machine",
                "• Python 3.14.8 64-bit",
                "• Security Middleware (nosniff, frame-deny)"
            ]},
            {"x": 880, "y": 140, "w": 280, "h": 180, "title": "Vision ML Process", "lines": ["• PyTorch 2.14.1+cpu", "• Ultralytics YOLOv8s", "• weights/best.pt (22.5 MB)", "• Mean latency: 344 ms"], "cls": "box-bg-highlight"},
            {"x": 880, "y": 380, "w": 280, "h": 220, "title": "Persistence Tier", "lines": ["• SQLite 3.50.4 (WAL Mode)", "• 9 Relational Tables", "• /uploads/reports/ (Public)", "• /uploads/evidence/ (Protected)"]},
        ],
        "arrows": [
            {"x1": 340, "y1": 220, "x2": 440, "y2": 260, "label": "HTTPS REST"},
            {"x1": 340, "y1": 480, "x2": 440, "y2": 440, "label": "HTTPS REST"},
            {"x1": 800, "y1": 260, "x2": 880, "y2": 220, "label": "Tensor Exec"},
            {"x1": 800, "y1": 420, "x2": 880, "y2": 440, "label": "SQLAlchemy"},
        ]
    }
]

# Write SVGs and render PNGs
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1200, "height": 800})

    for spec in diagram_specs:
        svg_content = make_svg(spec["title"], spec["subtitle"], spec["boxes"], spec["arrows"])
        svg_path = RENDERED_DIR / f"{spec['name']}.svg"
        png_path = RENDERED_DIR / f"{spec['name']}.png"

        # Save SVG
        with open(svg_path, "w", encoding="utf-8") as f:
            f.write(svg_content)

        # Render PNG via Playwright
        page.set_content(svg_content)
        page.wait_for_timeout(200)
        page.screenshot(path=str(png_path))
        print(f"[Rendered] {svg_path.name} and {png_path.name}")

    browser.close()

print("\nDiagram rendering complete!")
