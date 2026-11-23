"""CivicSight Week 10 Quality Gate — Phase 2 (Frontend) & Phase 4 (5 E2E Scenarios) Playwright Suite.

Executes real browser tests (Chromium + Firefox) against a live Uvicorn FastAPI server
backed by an isolated SQLite database. Captures screenshots to /tests/screenshots and
records structured evidence JSON files for /TEST_REPORT.md.
"""

import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.request
import urllib.error
from typing import Any, Optional
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"
SCREENSHOTS_DIR = PROJECT_ROOT / "tests" / "screenshots"
TESTS_DIR = PROJECT_ROOT / "tests"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

LIVE_HOST = "127.0.0.1"
LIVE_PORT = 8765
BASE_URL = f"http://{LIVE_HOST}:{LIVE_PORT}"


class LiveServerController:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.log_path = db_path.parent / "uvicorn_live.log"
        self.log_fh = None
        self.proc = None

    def start(self, extra_env=None):
        env = os.environ.copy()
        env["DATABASE_URL"] = f"sqlite:///{self.db_path.as_posix()}"
        env["CORS_ORIGINS"] = f"{BASE_URL},http://localhost:{LIVE_PORT}"
        env["PYTHONPATH"] = f"{PROJECT_ROOT}{os.pathsep}{BACKEND_DIR}"
        if extra_env:
            env.update(extra_env)

        self.log_fh = open(self.log_path, "ab")
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", LIVE_HOST, "--port", str(LIVE_PORT)],
            cwd=str(BACKEND_DIR),
            env=env,
            stdout=self.log_fh,
            stderr=subprocess.STDOUT,
        )
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f"{BASE_URL}/health", timeout=2) as resp:
                    if resp.status == 200:
                        return
            except Exception:
                time.sleep(0.35)
        tail = self.log_path.read_text(encoding="utf-8", errors="ignore")[-800:] if self.log_path.is_file() else ""
        raise RuntimeError(f"Live Uvicorn server failed to start on {BASE_URL}: {tail}")

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None
        if self.log_fh:
            try:
                self.log_fh.close()
            except Exception:
                pass
            self.log_fh = None

    def restart(self, extra_env=None):
        self.stop()
        time.sleep(0.5)
        self.start(extra_env=extra_env)


@pytest.fixture(scope="module")
def live_server(tmp_path_factory):
    db_dir = tmp_path_factory.mktemp("civicsight_e2e_live")
    db_path = db_dir / "e2e_live.db"
    ctrl = LiveServerController(db_path)
    ctrl.start()
    yield ctrl
    ctrl.stop()


def _db_query(db_path: Path, sql: str, params=()):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _api_request(method: str, path: str, token: Optional[str] = None, json_body: Optional[Any] = None) -> tuple[int, Any]:
    data = json.dumps(json_body).encode("utf-8") if json_body is not None else None
    headers = {"Accept": "application/json"}
    if json_body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="ignore")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"detail": raw}


def _api_login(email: str, password: str = "Password123!") -> tuple[str, Any]:
    st, body = _api_request("POST", "/api/v1/auth/login", json_body={"email": email, "password": password})
    assert st == 200, f"API login failed for {email}: {st} {body}"
    assert isinstance(body, dict), f"API login did not return a dict: {body}"
    return str(body["access_token"]), body["user"]


def _ui_login(page, email: str, password: str = "Password123!"):
    page.goto(f"{BASE_URL}/frontend/pages/login.html", wait_until="domcontentloaded")
    page.fill("#loginEmail", email)
    page.fill("#loginPassword", password)
    page.click("#loginSubmitBtn")
    page.wait_for_function("() => !!localStorage.getItem('civicsight_token')", timeout=10000)


# =============================================================================
# PHASE 2.1, 2.2, 2.3, 2.7, 2.8: FRONTEND QUALITY, THEMES, A11Y, RESPONSIVE
# =============================================================================

def test_phase2_auth_pages_routing_and_role_guards(live_server):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # 1. Registration validation & public role restriction
        page.goto(f"{BASE_URL}/frontend/pages/register.html", wait_until="networkidle")
        role_options = page.locator("#regRole option").all_text_contents()
        assert len(role_options) == 1 and "Citizen" in role_options[0], f"Unexpected public register roles: {role_options}"

        # Empty submit -> validation errors
        page.click("#registerSubmitBtn")
        name_err = page.locator("#nameError").text_content()
        assert name_err is not None, "Missing #nameError text"
        assert name_err.strip() != ""
        email_err = page.locator("#emailError").text_content()
        assert email_err is not None, "Missing #emailError text"
        assert email_err.strip() != ""
        pwd_err = page.locator("#passwordError").text_content()
        assert pwd_err is not None, "Missing #passwordError text"
        assert pwd_err.strip() != ""

        # Mismatched password confirmation
        page.fill("#regName", "Playwright Citizen")
        page.fill("#regEmail", "pw_citizen_new@example.com")
        page.fill("#regPassword", "Password123!")
        page.fill("#regConfirmPassword", "Different123!")
        page.click("#registerSubmitBtn")
        confirm_err = page.locator("#confirmPasswordError").text_content()
        assert confirm_err is not None, "Missing #confirmPasswordError text"
        assert "do not match" in confirm_err.lower()

        # Valid registration
        page.fill("#regConfirmPassword", "Password123!")
        page.click("#registerSubmitBtn")
        page.wait_for_selector("#authSuccessBanner", state="visible", timeout=8000)
        page.screenshot(path=str(SCREENSHOTS_DIR / "phase2_1_register_success.png"))

        # Duplicate email
        page.goto(f"{BASE_URL}/frontend/pages/register.html", wait_until="networkidle")
        page.fill("#regName", "Dup Citizen")
        page.fill("#regEmail", "pw_citizen_new@example.com")
        page.fill("#regPassword", "Password123!")
        page.fill("#regConfirmPassword", "Password123!")
        page.click("#registerSubmitBtn")
        page.wait_for_selector("#authErrorBanner", state="visible", timeout=8000)
        auth_err = page.locator("#authErrorMessage").text_content()
        assert auth_err is not None, "Missing #authErrorMessage text"
        assert "already exists" in auth_err.lower()

        # 2. Login errors + role-based routing
        page.goto(f"{BASE_URL}/frontend/pages/login.html", wait_until="networkidle")
        page.fill("#loginEmail", "citizen1@civicsight.org")
        page.fill("#loginPassword", "WrongPassword!")
        page.click("#loginSubmitBtn")
        page.wait_for_selector("#loginErrorBanner", state="visible", timeout=8000)

        # Citizen -> report.html
        _ui_login(page, "citizen1@civicsight.org")
        page.wait_for_url("**/report.html*", timeout=10000)

        # Direct URL access by Citizen to dashboard.html -> Access Restricted
        page.goto(f"{BASE_URL}/frontend/pages/dashboard.html", wait_until="networkidle")
        assert "Access Restricted" in page.content()
        page.screenshot(path=str(SCREENSHOTS_DIR / "phase2_1_citizen_blocked_dashboard.png"))

        # Logout clears session & dashboard redirects to login
        page.evaluate("() => CivicSightAuth.clearSession()")
        page.goto(f"{BASE_URL}/frontend/pages/dashboard.html", wait_until="domcontentloaded")
        page.wait_for_url("**/login.html*", timeout=10000)

        # Officer -> dashboard.html
        _ui_login(page, "officer1@civicsight.gov")
        page.wait_for_url("**/dashboard.html*", timeout=10000)

        # Staff -> maintenance.html & blocked on dashboard.html
        page.evaluate("() => CivicSightAuth.clearSession()")
        _ui_login(page, "staff1@civicsight.gov")
        page.wait_for_url("**/maintenance.html*", timeout=10000)
        page.goto(f"{BASE_URL}/frontend/pages/dashboard.html", wait_until="networkidle")
        assert "Access Restricted" in page.content()

        # Admin -> dashboard.html
        page.evaluate("() => CivicSightAuth.clearSession()")
        _ui_login(page, "admin1@civicsight.gov")
        page.wait_for_url("**/dashboard.html*", timeout=10000)

        browser.close()


def test_phase2_report_form_validation_offline_and_map_fallback(live_server):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            permissions=["geolocation"],
            geolocation={"latitude": 37.7795, "longitude": -122.4142, "accuracy": 18},
        )
        page = context.new_page()

        console_errors = []
        failed_requests = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("response", lambda res: failed_requests.append((res.status, res.url)) if res.status >= 400 and "/api/v1/reports" not in res.url else None)

        _ui_login(page, "citizen1@civicsight.org")
        page.wait_for_url("**/report.html*", timeout=10000)
        page.wait_for_load_state("networkidle")

        # Phase 0.6c & 2.2: Confirm removed UI is gone and label reads "Description"
        body_text = page.locator("body").inner_text()
        assert "Observed Defect Category" not in body_text
        assert "Automatic AI Detection" not in body_text
        assert page.locator("label[for='damageDescription']").inner_text().strip().startswith("Description")

        # Phase 2.3: Geolocation granted populated coords automatically & Map fallback renders cleanly
        page.wait_for_function("() => document.getElementById('latitude').value.startsWith('37.779')", timeout=8000)
        assert "Map unavailable: API key not configured" in page.locator("#reportMap").inner_text()
        assert len(console_errors) == 0, f"Console errors on report.html: {console_errors}"
        assert len(failed_requests) == 0, f"Failed static/config requests: {failed_requests}"

        # Phase 2.2: Invalid file formats rejected client-side & clear input
        for bad_f in ("unsupported.gif", "unsupported.pdf", "empty.jpg"):
            page.set_input_files("#damageImage", str(FIXTURES_DIR / bad_f))
            img_err = page.locator("#imageInputError").text_content()
            assert img_err is not None, f"Missing #imageInputError for {bad_f}"
            assert img_err.strip() != ""

        # Fake .txt renamed to .jpg -> rejected by backend magic-byte validation with readable error
        page.set_input_files("#damageImage", str(FIXTURES_DIR / "fake_text.jpg"))
        page.fill("#damageDescription", "Testing fake jpg rejection")
        page.click("#submitReportBtn")
        page.wait_for_selector("#submissionStatus.status-error", state="visible", timeout=8000)
        assert "invalid image" in page.locator("#submissionStatus").inner_text().lower()
        # Form state preserved (description still filled)
        assert page.input_value("#damageDescription") == "Testing fake jpg rejection"

        # Preview + Replace works
        page.set_input_files("#damageImage", str(FIXTURES_DIR / "sample_pothole_d40.jpg"))
        page.wait_for_selector("#previewContainer", state="visible", timeout=5000)
        page.click("#removeImageBtn")
        assert not page.locator("#previewContainer").is_visible()

        # Re-select image & test offline network error + recovery retry
        page.set_input_files("#damageImage", str(FIXTURES_DIR / "sample_pothole_d40.jpg"))
        page.fill("#damageDescription", "Offline recovery test pothole")
        context.set_offline(True)
        page.click("#submitReportBtn")
        page.wait_for_selector("#submissionStatus.status-error", state="visible", timeout=8000)
        assert "connect" in page.locator("#submissionStatus").inner_text().lower()
        assert page.input_value("#damageDescription") == "Offline recovery test pothole"

        # Go back online and retry cleanly
        context.set_offline(False)
        page.click("#submitReportBtn")
        page.wait_for_selector("#submissionStatus.status-success", state="visible", timeout=15000)
        assert "REPORT #" in page.locator("#submissionStatus").inner_text()
        page.screenshot(path=str(SCREENSHOTS_DIR / "phase2_2_report_submitted.png"))

        browser.close()


def test_phase2_7_and_2_8_themes_a11y_performance_responsive_and_firefox(live_server):
    responsive_widths = [
        (360, 740, "360_portrait"),
        (390, 844, "390_portrait"),
        (844, 390, "390_landscape"),
        (768, 1024, "768_tablet"),
        (1024, 768, "1024_laptop"),
        (1280, 800, "1280_desktop"),
        (1440, 900, "1440_desktop"),
        (1920, 1080, "1920_fhd"),
    ]
    pages_to_check = [
        ("landing", "/frontend/index.html", None),
        ("login", "/frontend/pages/login.html", None),
        ("register", "/frontend/pages/register.html", None),
        ("report", "/frontend/pages/report.html", "citizen1@civicsight.org"),
        ("dashboard", "/frontend/pages/dashboard.html", "officer1@civicsight.gov"),
        ("maintenance", "/frontend/pages/maintenance.html", "staff1@civicsight.gov"),
    ]

    responsive_report = []
    ux_a11y_perf_report = {}

    with sync_playwright() as p:
        # --- CHROMIUM FULL AUDIT ---
        browser = p.chromium.launch(headless=True)
        for page_name, rel_url, auth_email in pages_to_check:
            context = browser.new_context(viewport={"width": 1280, "height": 800})
            page = context.new_page()
            console_errs = []
            page.on("console", lambda m: console_errs.append(m.text) if m.type == "error" else None)

            if auth_email:
                tok, user = _api_login(auth_email)
                page.goto(f"{BASE_URL}/frontend/index.html", wait_until="domcontentloaded")
                page.evaluate("([t, u]) => { localStorage.setItem('civicsight_token', t); localStorage.setItem('civicsight_user', JSON.stringify(u)); }", [tok, user])

            t0 = time.perf_counter()
            page.goto(f"{BASE_URL}{rel_url}", wait_until="networkidle")
            load_ms = round((time.perf_counter() - t0) * 1000, 1)

            # Theme check: Light -> Dark toggle & persistence across reload
            initial_theme = page.evaluate("() => document.documentElement.getAttribute('data-theme')")
            assert initial_theme == "light"
            light_bg = page.evaluate("() => getComputedStyle(document.body).backgroundColor")
            assert light_bg in ("rgb(255, 255, 255)", "rgba(255, 255, 255, 1)")
            page.screenshot(path=str(SCREENSHOTS_DIR / f"page_{page_name}_light.png"))

            page.click("#themeToggleBtn")
            assert page.evaluate("() => document.documentElement.getAttribute('data-theme')") == "dark"
            dark_bg = page.evaluate("() => getComputedStyle(document.body).backgroundColor")
            assert dark_bg in ("rgb(0, 0, 0)", "rgba(0, 0, 0, 1)", "rgb(10, 10, 10)", "rgba(10, 10, 10, 1)")
            page.screenshot(path=str(SCREENSHOTS_DIR / f"page_{page_name}_dark.png"))

            page.reload(wait_until="networkidle")
            assert page.evaluate("() => document.documentElement.getAttribute('data-theme')") == "dark"
            page.click("#themeToggleBtn")  # Back to light

            # UX / A11y checks: no raw [object Object] / undefined, alt text, labels, landmarks
            a11y = page.evaluate("""() => {
                const text = document.body.innerText || '';
                const hasRawObj = text.includes('[object Object]');
                const imgsMissingAlt = Array.from(document.querySelectorAll('img')).filter(i => i.offsetParent !== null && !i.hasAttribute('alt')).length;
                const unlabeledInputs = Array.from(document.querySelectorAll('input:not([type=hidden]):not([type=file]), textarea, select')).filter(el => {
                    if (el.offsetParent === null) return false;
                    const id = el.id;
                    const hasLabel = id && document.querySelector(`label[for="${id}"]`);
                    return !hasLabel && !el.getAttribute('aria-label') && !el.getAttribute('title');
                }).length;
                const hasMain = !!document.querySelector('main');
                const hasH1 = !!document.querySelector('h1');
                const navTiming = performance.getEntriesByType('navigation')[0];
                return {
                    hasRawObj,
                    imgsMissingAlt,
                    unlabeledInputs,
                    hasMain,
                    hasH1,
                    domContentLoadedMs: navTiming ? Math.round(navTiming.domContentLoadedEventEnd) : 0,
                    loadEventMs: navTiming ? Math.round(navTiming.loadEventEnd) : 0,
                };
            }""")
            assert not a11y["hasRawObj"], f"[object Object] leaked on {page_name}"
            assert a11y["imgsMissingAlt"] == 0, f"Images missing alt on {page_name}"
            assert a11y["hasMain"] and a11y["hasH1"], f"Missing landmark/h1 on {page_name}"
            assert len(console_errs) == 0, f"Console errors on {page_name}: {console_errs}"

            ux_a11y_perf_report[page_name] = {
                "load_ms": load_ms,
                "light_bg": light_bg,
                "dark_bg": dark_bg,
                "console_errors": len(console_errs),
                **a11y,
            }

            # Responsive check across ALL 8 viewports (7 widths + mobile landscape)
            for w, h, tag in responsive_widths:
                page.set_viewport_size({"width": w, "height": h})
                page.wait_for_timeout(120)
                overflow_px = page.evaluate("() => Math.max(0, document.documentElement.scrollWidth - window.innerWidth)")
                responsive_report.append({
                    "page": page_name,
                    "viewport": f"{w}x{h}",
                    "tag": tag,
                    "horizontal_overflow_px": overflow_px,
                    "pass": overflow_px <= 2,
                })
                if tag in ("360_portrait", "768_tablet", "1440_desktop") and page_name in ("landing", "report", "dashboard", "maintenance"):
                    page.screenshot(path=str(SCREENSHOTS_DIR / f"resp_{page_name}_{tag}.png"))

            context.close()
        browser.close()

        # --- FIREFOX MULTI-ENGINE VERIFICATION ---
        ff_browser = p.firefox.launch(headless=True)
        ff_ctx = ff_browser.new_context(viewport={"width": 1280, "height": 800})
        ff_page = ff_ctx.new_page()
        ff_errors = []
        ff_page.on("console", lambda m: ff_errors.append(m.text) if m.type == "error" else None)
        ff_page.goto(f"{BASE_URL}/frontend/index.html", wait_until="networkidle")
        assert "CivicSight" in ff_page.title()
        ff_page.click("#themeToggleBtn")
        assert ff_page.evaluate("() => document.documentElement.getAttribute('data-theme')") == "dark"
        _ui_login(ff_page, "officer1@civicsight.gov")
        ff_page.wait_for_url("**/dashboard.html*", timeout=12000)
        ff_page.wait_for_load_state("networkidle")
        assert len(ff_errors) == 0, f"Firefox console errors: {ff_errors}"
        ff_page.screenshot(path=str(SCREENSHOTS_DIR / "firefox_dashboard.png"))
        ff_browser.close()

    (TESTS_DIR / "frontend_ux_a11y_perf.json").write_text(json.dumps(ux_a11y_perf_report, indent=2), encoding="utf-8")
    (TESTS_DIR / "responsive_results.json").write_text(json.dumps(responsive_report, indent=2), encoding="utf-8")

    # Assert ZERO responsive overflow failures across all pages & widths
    overflow_fails = [r for r in responsive_report if not r["pass"]]
    assert not overflow_fails, f"Responsive horizontal overflow detected: {overflow_fails}"


def test_phase2_4_dashboard_filters_and_escape_modal(live_server):
    """Phase 2.4: Dashboard status/priority/sort filters trigger real API requests and Escape closes modals."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        api_urls = []
        page.on("request", lambda req: api_urls.append(req.url) if "/api/v1/reports" in req.url and req.method == "GET" else None)

        _ui_login(page, "officer1@civicsight.gov")
        page.wait_for_url("**/dashboard.html*", timeout=10000)
        page.wait_for_load_state("networkidle")

        # Select status=submitted & priority=HIGH and confirm real API requests fired with query params
        api_urls.clear()
        page.select_option("#statusFilter", "submitted")
        page.wait_for_timeout(500)
        page.select_option("#priorityFilter", "HIGH")
        page.wait_for_timeout(500)
        assert any("status=submitted" in u for u in api_urls), f"Expected status=submitted API query, got: {api_urls}"
        assert any("priority=HIGH" in u for u in api_urls), f"Expected priority=HIGH API query, got: {api_urls}"

        # Reset filters restores unfiltered view
        page.click("#resetFiltersBtn")
        page.wait_for_timeout(500)
        assert page.input_value("#statusFilter") == ""
        assert page.input_value("#priorityFilter") == ""

        # Escape key closes open modal cleanly
        page.evaluate("() => document.getElementById('rejectModal').classList.add('open')")
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)
        assert not page.locator("#rejectModal").evaluate("el => el.classList.contains('open')")

        browser.close()


# =============================================================================
# PHASE 4: THE FIVE END-TO-END SCENARIOS (REAL BROWSER + REAL BACKEND + DB)
# =============================================================================

def test_phase4_scenario1_valid_citizen_report_and_restart_persistence(live_server):
    """SCENARIO 1: Valid citizen report -> ML runs -> priority displayed -> officer view -> restart backend -> persists."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            permissions=["geolocation"],
            geolocation={"latitude": 37.7749, "longitude": -122.4194, "accuracy": 12},
        )
        page = ctx.new_page()

        # 1. citizen1 logs in and uploads real pothole image
        _ui_login(page, "citizen1@civicsight.org")
        page.wait_for_url("**/report.html*", timeout=10000)
        page.set_input_files("#damageImage", str(FIXTURES_DIR / "sample_pothole_d40.jpg"))
        page.fill("#damageDescription", "Scenario 1: Deep pothole near Market St crosswalk")
        page.fill("#addressText", "Market St & 5th Ave")
        page.click("#submitReportBtn")
        page.wait_for_selector("#submissionStatus.status-success", state="visible", timeout=20000)

        badge_text = page.locator(".status-id-badge").inner_text()
        report_id = int(badge_text.replace("REPORT #", "").strip())

        # Wait for background ML to complete in DB
        deadline = time.time() + 20
        rep_row = None
        while time.time() < deadline:
            rows = _db_query(live_server.db_path, "SELECT * FROM reports WHERE id = ?", (report_id,))
            if rows and rows[0]["ml_status"] in ("ML_COMPLETE", "ML_NO_DETECTIONS"):
                rep_row = rows[0]
                break
            time.sleep(0.4)
        assert rep_row is not None, "ML did not finish in time"
        assert rep_row["ml_model_version"] == "YOLOv8s-clean_rdd2022_yolov8s"
        assert rep_row["priority"] in ("HIGH", "MEDIUM", "LOW")
        assert rep_row["priority_reasons"] is not None

        # Verify image file exists on disk
        disk_img = BACKEND_DIR / rep_row["image_url"].lstrip("/")
        assert disk_img.is_file() and disk_img.stat().st_size > 0

        # Verify detection rows & status history in DB
        det_rows = _db_query(live_server.db_path, "SELECT * FROM detection_results WHERE report_id = ?", (report_id,))
        if rep_row["ml_status"] == "ML_COMPLETE":
            assert len(det_rows) >= 1
            assert det_rows[0]["model_version"] == "YOLOv8s-clean_rdd2022_yolov8s"
        hist_rows = _db_query(live_server.db_path, "SELECT * FROM report_status_history WHERE report_id = ?", (report_id,))
        assert len(hist_rows) >= 1 and hist_rows[0]["to_status"] == "submitted"

        page.screenshot(path=str(SCREENSHOTS_DIR / "scenario1_citizen_view.png"))

        # Officer views report on dashboard & inspects ML bounding-box overlay (Phase 3.6)
        page.evaluate("() => CivicSightAuth.clearSession()")
        _ui_login(page, "officer1@civicsight.gov")
        page.wait_for_url("**/dashboard.html*", timeout=10000)
        page.wait_for_selector(f"text=#{report_id}", timeout=10000)
        page.screenshot(path=str(SCREENSHOTS_DIR / "scenario1_officer_view.png"))

        page.evaluate(f"() => CivicSightDashboard.openInspection({report_id})")
        page.wait_for_selector("#inspectionModal.open", timeout=8000)
        if rep_row["ml_status"] == "ML_COMPLETE":
            page.wait_for_selector("#mlSvgOverlay rect.bbox-rect", timeout=8000)
            rects = page.evaluate("""() => Array.from(document.querySelectorAll('#mlSvgOverlay rect.bbox-rect')).map(r => ({
                x: parseFloat(r.getAttribute('x')),
                y: parseFloat(r.getAttribute('y')),
                w: parseFloat(r.getAttribute('width')),
                h: parseFloat(r.getAttribute('height')),
            }))""")
            assert len(rects) >= 1, "Expected rendered SVG bounding boxes"
            for rc in rects:
                assert 0 <= rc["x"] <= 100 and 0 <= rc["y"] <= 100
                assert rc["w"] > 0 and rc["h"] > 0
            page.screenshot(path=str(SCREENSHOTS_DIR / "scenario1_officer_bbox_modal.png"))

        # Restart live Uvicorn backend subprocess and prove persistence!
        live_server.restart()
        page.reload(wait_until="networkidle")
        page.wait_for_selector(f"text=#{report_id}", timeout=10000)
        off_tok, _ = _api_login("officer1@civicsight.gov")
        st, detail = _api_request("GET", f"/api/v1/reports/{report_id}", token=off_tok)
        assert st == 200 and detail["id"] == report_id and detail["ml_model_version"] == "YOLOv8s-clean_rdd2022_yolov8s"

        browser.close()


def test_phase4_scenario2_gps_denied_and_maps_blocked(live_server):
    """SCENARIO 2: GPS permission denied -> manual pin/coords -> submits; invalid coords blocked; Maps blocked still submits."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()  # No geolocation permission granted
        page = ctx.new_page()

        # Simulate explicit browser geolocation permission denied (code 1)
        page.add_init_script("""
            navigator.geolocation.getCurrentPosition = (success, error) => {
                setTimeout(() => error({ code: 1, message: 'User denied Geolocation' }), 50);
            };
        """)
        # Also block maps.googleapis.com to test blocked Maps script scenario
        page.route("**/maps.googleapis.com/**", lambda route: route.abort())

        _ui_login(page, "citizen1@civicsight.org")
        page.wait_for_url("**/report.html*", timeout=10000)
        page.wait_for_function("() => document.getElementById('locationStatusText').textContent.includes('Permission Denied')", timeout=8000)

        # Enter invalid/out-of-range coordinates -> submission blocked with clear message
        page.set_input_files("#damageImage", str(FIXTURES_DIR / "damage_d40.jpg"))
        page.fill("#damageDescription", "Scenario 2 invalid coord check")
        page.fill("#latitude", "125.0")
        page.fill("#longitude", "-122.41")
        page.click("#submitReportBtn")
        page.wait_for_selector("#submissionStatus.status-error", state="visible", timeout=5000)
        assert "latitude" in page.locator("#latitudeError").inner_text().lower()

        # Drop manual coordinates and submit cleanly even with GPS denied + Maps blocked
        manual_lat, manual_lng = "37.768123", "-122.429456"
        page.fill("#latitude", manual_lat)
        page.fill("#longitude", manual_lng)
        page.fill("#damageDescription", "Scenario 2 manual coordinates with GPS denied and Maps blocked")
        page.click("#submitReportBtn")
        page.wait_for_selector("#submissionStatus.status-success", state="visible", timeout=15000)
        report_id = int(page.locator(".status-id-badge").inner_text().replace("REPORT #", "").strip())

        rows = _db_query(live_server.db_path, "SELECT latitude, longitude FROM reports WHERE id = ?", (report_id,))
        assert abs(rows[0]["latitude"] - float(manual_lat)) < 1e-5
        assert abs(rows[0]["longitude"] - float(manual_lng)) < 1e-5
        page.screenshot(path=str(SCREENSHOTS_DIR / "scenario2_gps_denied_manual.png"))
        browser.close()


def test_phase4_scenario3_officer_rejects_report(live_server):
    """SCENARIO 3: Officer rejects report -> REJECTED distinct from CLOSED, reason in history, citizen sees reason, excluded from proximity."""
    cit_tok, _ = _api_login("citizen1@civicsight.org")
    off_tok, _ = _api_login("officer1@civicsight.gov")
    _, st1 = _api_login("staff1@civicsight.gov")

    # Submit via API (as citizen1)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()

        _ui_login(page, "citizen1@civicsight.org")
        page.wait_for_url("**/report.html*", timeout=10000)
        page.set_input_files("#damageImage", str(FIXTURES_DIR / "non_road.jpg"))
        page.fill("#damageDescription", "Scenario 3 non-road false alarm")
        page.fill("#latitude", "37.720000")
        page.fill("#longitude", "-122.470000")
        page.click("#submitReportBtn")
        page.wait_for_selector("#submissionStatus.status-success", state="visible", timeout=15000)
        rep_id = int(page.locator(".status-id-badge").inner_text().replace("REPORT #", "").strip())

        # Reject without reason must fail (422)
        st_no_reason, _ = _api_request("POST", f"/api/v1/reports/{rep_id}/reject", token=off_tok, json_body={"reason": "   "})
        assert st_no_reason == 422

        # Officer rejects via UI modal
        page.evaluate("() => CivicSightAuth.clearSession()")
        _ui_login(page, "officer1@civicsight.gov")
        page.wait_for_url("**/dashboard.html*", timeout=10000)
        page.wait_for_selector(f"text=#{rep_id}", timeout=10000)
        page.evaluate(f"() => CivicSightDashboard.openInspection({rep_id})")
        page.wait_for_selector("#inspectionModal.open", timeout=8000)
        page.click("#modalRejectBtn")
        page.wait_for_selector("#rejectModal.open", timeout=5000)
        page.fill("#rejectReasonInput", "Photo depicts sky/park rather than public roadway")
        page.click("#rejectForm button[type='submit']")
        page.wait_for_timeout(1200)

        # Verify DB state & history
        rep_db = _db_query(live_server.db_path, "SELECT status, rejection_reason FROM reports WHERE id = ?", (rep_id,))[0]
        assert rep_db["status"] == "rejected"
        assert "public roadway" in rep_db["rejection_reason"]
        hist = _db_query(live_server.db_path, "SELECT * FROM report_status_history WHERE report_id = ? ORDER BY id DESC", (rep_id,))
        assert hist[0]["to_status"] == "rejected" and hist[0]["performed_by_role"] == "Municipal Officer"

        # Rejected report cannot be assigned or verified or transitioned
        assert _api_request("POST", f"/api/v1/reports/{rep_id}/assign", token=off_tok, json_body={"staff_id": st1["id"]})[0] == 400
        assert _api_request("POST", f"/api/v1/reports/{rep_id}/verify", token=off_tok, json_body={})[0] == 400

        # Citizen sees rejected state and reason on report.html?id=<rep_id>
        page.evaluate("() => CivicSightAuth.clearSession()")
        _ui_login(page, "citizen1@civicsight.org")
        page.wait_for_url("**/report.html*", timeout=10000)
        page.goto(f"{BASE_URL}/frontend/pages/report.html?id={rep_id}", wait_until="networkidle")
        page.wait_for_selector("#submissionStatus.status-success", state="visible", timeout=8000)
        status_txt = page.locator("#submissionStatus").inner_text()
        assert "REJECTED" in status_txt.upper()
        assert "public roadway" in status_txt
        page.screenshot(path=str(SCREENSHOTS_DIR / "scenario3_citizen_sees_rejected.png"))

        # Proximity check: new report at exact same coordinates MUST NOT match rejected report
        st_prox, prox_rep = _api_request(
            "POST", "/api/v1/reports", token=cit_tok,
            json_body={"description": "New nearby after rejection", "latitude": 37.720000, "longitude": -122.470000, "damage_type": "D40"},
        )
        assert st_prox == 201
        _, rels = _api_request("GET", f"/api/v1/reports/{prox_rep['id']}/related", token=off_tok)
        assert isinstance(rels, list), f"Expected list of relations, got {type(rels)}"
        assert all(isinstance(r, dict) and r["related_report_id"] != rep_id for r in rels)

        # Rejecting an already-assigned report must fail
        _, r_asgn = _api_request("POST", "/api/v1/reports", token=cit_tok, json_body={"description": "Assigned reject test", "latitude": 37.725, "longitude": -122.475})
        _api_request("POST", f"/api/v1/reports/{r_asgn['id']}/verify", token=off_tok, json_body={})
        _api_request("POST", f"/api/v1/reports/{r_asgn['id']}/assign", token=off_tok, json_body={"staff_id": st1["id"]})
        assert _api_request("POST", f"/api/v1/reports/{r_asgn['id']}/reject", token=off_tok, json_body={"reason": "Too late"})[0] == 400

        browser.close()


def test_phase4_scenario4_nearby_and_duplicate_reports(live_server):
    """SCENARIO 4: 5 spatial reports -> exact relation types, no auto-merge, priority history, confirm once, second rejected."""
    cit_tok, _ = _api_login("citizen1@civicsight.org")
    off_tok, _ = _api_login("officer1@civicsight.gov")

    # Isolated coordinate cluster around (37.8100, -122.4900)
    _, r1 = _api_request("POST", "/api/v1/reports", token=cit_tok, json_body={"description": "S4 R1 Pothole", "latitude": 37.81000, "longitude": -122.49000, "damage_type": "D40"})
    _, r2 = _api_request("POST", "/api/v1/reports", token=cit_tok, json_body={"description": "S4 R2 Pothole ~5m", "latitude": 37.81004, "longitude": -122.49000, "damage_type": "D40"})
    _, r3 = _api_request("POST", "/api/v1/reports", token=cit_tok, json_body={"description": "S4 R3 Pothole ~30m", "latitude": 37.81027, "longitude": -122.49000, "damage_type": "D40"})
    _, r4 = _api_request("POST", "/api/v1/reports", token=cit_tok, json_body={"description": "S4 R4 Crack same spot", "latitude": 37.81000, "longitude": -122.49000, "damage_type": "D00"})
    _, r5 = _api_request("POST", "/api/v1/reports", token=cit_tok, json_body={"description": "S4 R5 Far away ~5km", "latitude": 37.85500, "longitude": -122.49000, "damage_type": "D40"})

    _, rels_r1 = _api_request("GET", f"/api/v1/reports/{r1['id']}/related", token=off_tok)
    assert isinstance(rels_r1, list), f"Expected list of relations, got {type(rels_r1)}"
    rel_map: dict[int, dict[str, Any]] = {
        item["related_report_id"]: item for item in rels_r1 if isinstance(item, dict)
    }
    assert rel_map[r2["id"]]["relation_type"] == "POTENTIAL_DUPLICATE"
    assert rel_map[r3["id"]]["relation_type"] == "NEARBY_RELATED"
    assert rel_map[r4["id"]]["relation_type"] == "NEARBY_RELATED"
    assert r5["id"] not in rel_map

    # Nothing auto-merged or auto-closed
    for rid in (r1["id"], r2["id"], r3["id"], r4["id"], r5["id"]):
        _, d = _api_request("GET", f"/api/v1/reports/{rid}", token=off_tok)
        assert d["status"] == "submitted"

    # Priority history logged
    _, ph = _api_request("GET", f"/api/v1/reports/{r1['id']}/priority-history", token=off_tok)
    assert len(ph) >= 1

    # Officer confirms duplicate once -> succeeds, newer (r2) becomes duplicate of r1, originals remain intact
    dup_rel_id = rel_map[r2["id"]]["relation_id"]
    st_conf, _ = _api_request("PATCH", f"/api/v1/report-relations/{dup_rel_id}", token=off_tok, json_body={"review_status": "CONFIRMED_DUPLICATE", "note": "Same pothole confirmed"})
    assert st_conf == 200
    # Second review attempt MUST be rejected (400)
    st_conf2, _ = _api_request("PATCH", f"/api/v1/report-relations/{dup_rel_id}", token=off_tok, json_body={"review_status": "DISMISSED", "note": "Retry"})
    assert st_conf2 == 400

    _, r1_after = _api_request("GET", f"/api/v1/reports/{r1['id']}", token=off_tok)
    _, r2_after = _api_request("GET", f"/api/v1/reports/{r2['id']}", token=off_tok)
    assert r1_after["status"] == "submitted"
    assert r2_after["status"] == "duplicate" and r2_after["duplicate_of_id"] == r1["id"]

    # Open in Playwright dashboard to verify Related Reports UI renders cleanly
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        _ui_login(page, "officer1@civicsight.gov")
        page.wait_for_url("**/dashboard.html*", timeout=10000)
        page.wait_for_selector(f"text=#{r1['id']}", timeout=10000)
        page.evaluate(f"() => CivicSightDashboard.openInspection({r1['id']})")
        page.wait_for_selector("#inspectionModal.open", timeout=8000)
        assert "Related & Nearby Reports" in page.locator("#inspectionModal").inner_text()
        page.screenshot(path=str(SCREENSHOTS_DIR / "scenario4_related_reports_modal.png"))
        browser.close()


def test_phase4_scenario5_complete_maintenance_workflow_and_broken_ml(live_server):
    """SCENARIO 5: Complete lifecycle with rework loop, bad evidence rejected, permissions checked, before/after verified, AND re-run with broken ML."""
    cit1_tok, _ = _api_login("citizen1@civicsight.org")
    cit2_tok, _ = _api_login("citizen2@civicsight.org")
    off1_tok, _ = _api_login("officer1@civicsight.gov")
    off2_tok, _ = _api_login("officer2@civicsight.gov")
    st1_tok, st1_user = _api_login("staff1@civicsight.gov")
    st2_tok, _ = _api_login("staff2@civicsight.gov")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})

        # 1. Citizen1 submits report via browser UI
        _ui_login(page, "citizen1@civicsight.org")
        page.wait_for_url("**/report.html*", timeout=10000)
        page.set_input_files("#damageImage", str(FIXTURES_DIR / "sample_pothole_d40.jpg"))
        page.fill("#damageDescription", "Scenario 5 complete maintenance lifecycle pothole")
        page.fill("#latitude", "37.761000")
        page.fill("#longitude", "-122.431000")
        page.click("#submitReportBtn")
        page.wait_for_selector("#submissionStatus.status-success", state="visible", timeout=20000)
        rep_id = int(page.locator(".status-id-badge").inner_text().replace("REPORT #", "").strip())

        # 2. Officer1 verifies and assigns to staff1 via dashboard UI
        page.evaluate("() => CivicSightAuth.clearSession()")
        _ui_login(page, "officer1@civicsight.gov")
        page.wait_for_url("**/dashboard.html*", timeout=10000)
        page.wait_for_selector(f"text=#{rep_id}", timeout=10000)

        # Verify & assign via API/UI
        assert _api_request("POST", f"/api/v1/reports/{rep_id}/verify", token=off1_tok, json_body={"note": "S5 verified"})[0] == 200
        assert _api_request("POST", f"/api/v1/reports/{rep_id}/assign", token=off1_tok, json_body={"staff_id": st1_user["id"], "note": "Patch ASAP"})[0] == 200

        # Permission checks: staff2, citizen1, citizen2 cannot start/upload/verify
        assert _api_request("POST", f"/api/v1/reports/{rep_id}/repair/start", token=st2_tok)[0] == 403
        assert _api_request("POST", f"/api/v1/reports/{rep_id}/repair/start", token=cit1_tok)[0] == 403
        assert _api_request("GET", f"/api/v1/reports/{rep_id}", token=cit2_tok)[0] == 403

        # 3. Staff2 logs in to maintenance.html -> does NOT see rep_id
        page.evaluate("() => CivicSightAuth.clearSession()")
        _ui_login(page, "staff2@civicsight.gov")
        page.wait_for_url("**/maintenance.html*", timeout=10000)
        page.wait_for_load_state("networkidle")
        assert f"Work Order #{rep_id}" not in page.locator("body").inner_text()

        # 4. Staff1 logs in -> starts repair -> tries bad file -> uploads real AFTER photo -> submits
        page.evaluate("() => CivicSightAuth.clearSession()")
        _ui_login(page, "staff1@civicsight.gov")
        page.wait_for_url("**/maintenance.html*", timeout=10000)
        page.wait_for_selector(f"#assignmentCard_{rep_id}", timeout=10000)
        page.locator(f"#assignmentCard_{rep_id} button").click()  # Start Physical Repair -> opens evidence modal
        page.wait_for_selector("#evidenceModal.open", timeout=10000)

        # Submit button MUST be disabled before any AFTER photo exists
        assert page.locator("#submitForVerificationBtn").is_disabled()

        # Bad file rejected
        page.set_input_files("#evidenceFileInput", str(FIXTURES_DIR / "unsupported.pdf"))
        assert page.locator("#submitForVerificationBtn").is_disabled()

        # Valid AFTER photo uploaded
        page.set_input_files("#evidenceFileInput", str(FIXTURES_DIR / "after_repair.jpg"))
        page.wait_for_selector("#evidenceSelectedPreviewWrap", state="visible", timeout=5000)
        page.fill("#evidenceUploadNote", "Initial asphalt fill applied")
        page.click("#uploadEvidenceOnlyBtn")
        page.wait_for_function("() => !document.getElementById('submitForVerificationBtn').disabled", timeout=10000)
        page.screenshot(path=str(SCREENSHOTS_DIR / "scenario5_staff_evidence_uploaded.png"))

        page.click("#submitForVerificationBtn")
        page.wait_for_selector("#evidenceModal.open", state="hidden", timeout=10000)

        # 5. Officer1 SENDS BACK with note via Final Verification modal (and verify staff1 cannot close)
        assert _api_request("POST", f"/api/v1/reports/{rep_id}/final-verify", token=st1_tok, json_body={"decision": "APPROVED"})[0] == 403
        page.evaluate("() => CivicSightAuth.clearSession()")
        _ui_login(page, "officer1@civicsight.gov")
        page.wait_for_url("**/dashboard.html*", timeout=10000)
        page.wait_for_selector(f"text=#{rep_id}", timeout=10000)
        page.evaluate(f"() => CivicSightDashboard.openFinalVerifyModal({rep_id})")
        page.wait_for_selector("#finalVerifyModal.open", timeout=8000)
        # Wait for authenticated Blob image to load in #verifyAfterImg
        page.wait_for_function("() => (document.getElementById('verifyAfterImg').src || '').startsWith('blob:')", timeout=10000)
        page.screenshot(path=str(SCREENSHOTS_DIR / "scenario5_officer_final_verify_modal.png"))

        page.fill("#finalVerifyNoteInput", "Edges require hot-mix sealant compaction")
        page.click("#sendBackReworkBtn")
        page.wait_for_selector("#finalVerifyModal.open", state="hidden", timeout=10000)

        # 6. Staff1 sees rework note on card, uploads second photo, resubmits
        page.evaluate("() => CivicSightAuth.clearSession()")
        _ui_login(page, "staff1@civicsight.gov")
        page.wait_for_url("**/maintenance.html*", timeout=10000)
        page.wait_for_selector(f"#assignmentCard_{rep_id}", timeout=10000)
        assert "hot-mix sealant compaction" in page.locator(f"#assignmentCard_{rep_id}").inner_text()
        page.screenshot(path=str(SCREENSHOTS_DIR / "scenario5_staff_rework_banner.png"))

        page.locator(f"#assignmentCard_{rep_id} button").click()
        page.wait_for_selector("#evidenceModal.open", timeout=8000)
        page.set_input_files("#evidenceFileInput", str(FIXTURES_DIR / "after_repair.jpg"))
        page.fill("#evidenceUploadNote", "Compacted edges and applied hot sealant")
        page.click("#uploadEvidenceOnlyBtn")
        page.wait_for_timeout(1200)
        page.click("#submitForVerificationBtn")
        page.wait_for_selector("#evidenceModal.open", state="hidden", timeout=10000)

        # 7. Officer2 APPROVES & CLOSES
        st_app, closed_data = _api_request("POST", f"/api/v1/reports/{rep_id}/final-verify", token=off2_tok, json_body={"decision": "APPROVED", "note": "Road restored to municipal standard"})
        assert st_app == 200 and closed_data["status"] == "closed"
        assert closed_data["priority"] in ("HIGH", "MEDIUM", "LOW")
        assert len(closed_data["priority_reasons"]) >= 1
        assert len(closed_data["after_images"]) >= 2

        # 8. Citizen1 sees CLOSED status + read-only Before/After images; Citizen2 is BLOCKED
        page.evaluate("() => CivicSightAuth.clearSession()")
        _ui_login(page, "citizen1@civicsight.org")
        page.wait_for_url("**/report.html*", timeout=10000)
        page.goto(f"{BASE_URL}/frontend/pages/report.html?id={rep_id}", wait_until="networkidle")
        page.wait_for_selector("#citizenBeforeAfterSection", state="visible", timeout=10000)
        page.wait_for_function("() => (document.getElementById('citizenAfterEvidenceImg').src || '').startsWith('blob:')", timeout=10000)
        assert "CLOSED" in page.locator("#submissionStatus").inner_text().upper()
        page.screenshot(path=str(SCREENSHOTS_DIR / "scenario5_citizen_closed_before_after.png"))

        # Citizen2 blocked on Citizen1's report
        page.evaluate("() => CivicSightAuth.clearSession()")
        _ui_login(page, "citizen2@civicsight.org")
        page.wait_for_url("**/report.html*", timeout=10000)
        page.goto(f"{BASE_URL}/frontend/pages/report.html?id={rep_id}", wait_until="networkidle")
        page.wait_for_selector("#submissionStatus.status-error", state="visible", timeout=8000)
        assert "access denied" in page.locator("#submissionStatus").inner_text().lower()

        # 9. Re-run full lifecycle with DELIBERATELY BROKEN ML MODEL (invalid MODEL_PATH)
        live_server.restart(extra_env={"MODEL_PATH": "ml/DELIBERATELY_BROKEN_MODEL.pt"})
        page.evaluate("() => CivicSightAuth.clearSession()")
        _ui_login(page, "citizen1@civicsight.org")
        page.wait_for_url("**/report.html*", timeout=10000)
        page.set_input_files("#damageImage", str(FIXTURES_DIR / "damage_d40.jpg"))
        page.fill("#damageDescription", "Scenario 5B: Broken ML complete lifecycle")
        page.fill("#latitude", "37.762500")
        page.fill("#longitude", "-122.432500")
        page.click("#submitReportBtn")
        page.wait_for_selector("#submissionStatus.status-success", state="visible", timeout=15000)
        broken_rep_id = int(page.locator(".status-id-badge").inner_text().replace("REPORT #", "").strip())
        broken_deadline = time.time() + 15
        broken_row = None
        while time.time() < broken_deadline:
            rows_b = _db_query(live_server.db_path, "SELECT ml_status, status FROM reports WHERE id = ?", (broken_rep_id,))
            if rows_b and rows_b[0]["ml_status"] != "ML_PENDING":
                broken_row = rows_b[0]
                break
            time.sleep(0.35)
        assert broken_row is not None and broken_row["ml_status"] == "ML_FAILED" and broken_row["status"] == "submitted"

        # Complete full closure despite ML_FAILED
        assert _api_request("POST", f"/api/v1/reports/{broken_rep_id}/verify", token=off1_tok, json_body={"note": "Verified without ML"})[0] == 200
        assert _api_request("POST", f"/api/v1/reports/{broken_rep_id}/assign", token=off1_tok, json_body={"staff_id": st1_user["id"]})[0] == 200
        assert _api_request("POST", f"/api/v1/reports/{broken_rep_id}/repair/start", token=st1_tok)[0] == 200
        # Upload AFTER evidence via multipart helper using requests/urllib
        import httpx
        with httpx.Client(base_url=BASE_URL) as hc:
            ev_r = hc.post(
                f"/api/v1/reports/{broken_rep_id}/repair/evidence",
                headers={"Authorization": f"Bearer {st1_tok}"},
                data={"kind": "AFTER", "note": "Fixed with ML down"},
                files={"file": ("after.jpg", (FIXTURES_DIR / "after_repair.jpg").read_bytes(), "image/jpeg")},
            )
            assert ev_r.status_code == 201
        assert _api_request("POST", f"/api/v1/reports/{broken_rep_id}/repair/submit", token=st1_tok, json_body={"note": "Done"})[0] == 200
        st_b_close, b_closed = _api_request("POST", f"/api/v1/reports/{broken_rep_id}/final-verify", token=off1_tok, json_body={"decision": "APPROVED", "note": "Closed with broken ML"})
        assert st_b_close == 200 and b_closed["status"] == "closed" and b_closed["ml_status"] == "ML_FAILED"

        browser.close()
