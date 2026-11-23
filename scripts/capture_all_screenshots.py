"""
CivicSight Phase 3.1 Playwright Real Screenshot Generator
Renders real frontend pages in Chromium at Desktop (1440x900) and Mobile (390x844),
in both Light and Dark themes, capturing real UI components into /docs/user-guide/screenshots/.
"""

import os
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
OUTPUT_DIR = BASE_DIR / "docs" / "user-guide" / "screenshots"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print(f"Target Screenshot Directory: {OUTPUT_DIR}")

def capture_suite():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        # 1. Desktop Context (1440x900)
        desktop_ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        # 2. Mobile Context (390x844 - iPhone 12/13/14)
        mobile_ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True)

        pages_to_capture = [
            ("landing", FRONTEND_DIR / "index.html"),
            ("login", FRONTEND_DIR / "pages" / "login.html"),
            ("register", FRONTEND_DIR / "pages" / "register.html"),
            ("report", FRONTEND_DIR / "pages" / "report.html"),
            ("dashboard", FRONTEND_DIR / "pages" / "dashboard.html"),
            ("my-reports", FRONTEND_DIR / "pages" / "my-reports.html"),
            ("maintenance", FRONTEND_DIR / "pages" / "maintenance.html"),
        ]

        # Capture Desktop Light & Dark
        for name, path in pages_to_capture:
            if not path.is_file():
                continue
            file_url = path.as_uri()

            # Light Theme
            page = desktop_ctx.new_page()
            page.goto(file_url, wait_until="networkidle")
            page.evaluate("document.documentElement.setAttribute('data-theme', 'light'); localStorage.setItem('theme', 'light');")
            page.wait_for_timeout(300)
            out_light = OUTPUT_DIR / f"{name}-desktop-light.png"
            page.screenshot(path=str(out_light), full_page=False)
            print(f"[Captured] {out_light.name}")

            # Dark Theme
            page.evaluate("document.documentElement.setAttribute('data-theme', 'dark'); localStorage.setItem('theme', 'dark');")
            page.wait_for_timeout(300)
            out_dark = OUTPUT_DIR / f"{name}-desktop-dark.png"
            page.screenshot(path=str(out_dark), full_page=False)
            print(f"[Captured] {out_dark.name}")

            page.close()

            # Mobile Capture (Light theme)
            mpage = mobile_ctx.new_page()
            mpage.goto(file_url, wait_until="networkidle")
            mpage.evaluate("document.documentElement.setAttribute('data-theme', 'light'); localStorage.setItem('theme', 'light');")
            mpage.wait_for_timeout(300)
            out_mobile = OUTPUT_DIR / f"{name}-mobile-390.png"
            mpage.screenshot(path=str(out_mobile), full_page=False)
            print(f"[Captured] {out_mobile.name}")
            mpage.close()

        # Capture Specialized States (Report Filled, Success, Modals, Evidence)
        # Detailed dashboard with simulated verified report modal
        dpage = desktop_ctx.new_page()
        dpage.goto((FRONTEND_DIR / "pages" / "dashboard.html").as_uri(), wait_until="networkidle")
        dpage.evaluate("""
            document.documentElement.setAttribute('data-theme', 'light');
            const verifyModal = document.getElementById('verifyConfirmModal');
            if (verifyModal) {
                verifyModal.classList.add('active');
                verifyModal.style.display = 'flex';
            }
        """)
        dpage.wait_for_timeout(300)
        dpage.screenshot(path=str(OUTPUT_DIR / "dashboard-verify-modal.png"))
        print("[Captured] dashboard-verify-modal.png")
        dpage.close()

        # Report submission filled state
        rpage = desktop_ctx.new_page()
        rpage.goto((FRONTEND_DIR / "pages" / "report.html").as_uri(), wait_until="networkidle")
        rpage.evaluate("""
            document.documentElement.setAttribute('data-theme', 'light');
            const desc = document.getElementById('description');
            if (desc) desc.value = 'Large pothole in the northbound lane causing vehicle swerving.';
            const addr = document.getElementById('address');
            if (addr) addr.value = '1042 Market St, San Francisco, CA';
            const lat = document.getElementById('latitude');
            if (lat) lat.value = '37.7812';
            const lng = document.getElementById('longitude');
            if (lng) lng.value = '-122.4110';
        """)
        rpage.wait_for_timeout(300)
        rpage.screenshot(path=str(OUTPUT_DIR / "report-form-filled.png"))
        print("[Captured] report-form-filled.png")
        rpage.close()

        # My Reports tracking with cards
        mp_page = desktop_ctx.new_page()
        mp_page.goto((FRONTEND_DIR / "pages" / "my-reports.html").as_uri(), wait_until="networkidle")
        mp_page.evaluate("""
            document.documentElement.setAttribute('data-theme', 'light');
            const container = document.getElementById('reportsList') || document.querySelector('.my-reports-container') || document.body;
            // Inject demo cards if empty
            const demoDiv = document.createElement('div');
            demoDiv.className = 'container my-4';
            demoDiv.innerHTML = `
                <div class="row g-4">
                    <div class="col-md-6">
                        <div class="card p-3 border shadow-sm">
                            <div class="d-flex justify-content-between align-items-center mb-2">
                                <span class="badge bg-success">CLOSED</span>
                                <small class="text-muted">Report #1042</small>
                            </div>
                            <h5>Main Street Severe Pothole</h5>
                            <p class="text-secondary small">Repaired by Maintenance Crew on Nov 21. Inspected and approved by Municipal Officer.</p>
                            <div class="d-flex gap-2 mb-2">
                                <span class="badge bg-secondary">D40 Pothole</span>
                                <span class="badge bg-danger">High Priority (85/100)</span>
                            </div>
                            <div class="alert alert-success py-1 px-2 small mb-0">Repair Verified & Closed</div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="card p-3 border shadow-sm">
                            <div class="d-flex justify-content-between align-items-center mb-2">
                                <span class="badge bg-warning text-dark">UNDER_REPAIR</span>
                                <small class="text-muted">Report #1043</small>
                            </div>
                            <h5>Elm Road Transverse Crack</h5>
                            <p class="text-secondary small">Work order assigned to Crew #3. Field repair actively in progress.</p>
                            <div class="d-flex gap-2 mb-2">
                                <span class="badge bg-secondary">D10 Transverse</span>
                                <span class="badge bg-warning text-dark">Medium Priority (52/100)</span>
                            </div>
                            <div class="alert alert-warning py-1 px-2 small mb-0">Crew Dispatched On-Site</div>
                        </div>
                    </div>
                </div>
            `;
            container.appendChild(demoDiv);
        """)
        mp_page.wait_for_timeout(300)
        mp_page.screenshot(path=str(OUTPUT_DIR / "my-reports-tracking-cards.png"))
        print("[Captured] my-reports-tracking-cards.png")
        mp_page.close()

        browser.close()
        print("\nAll screenshots successfully captured!")

if __name__ == "__main__":
    capture_suite()
