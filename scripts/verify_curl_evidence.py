"""Week 10 Phase 1 manual curl.exe verification helper (runs against isolated temp SQLite DB)."""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"


def main():
    td = tempfile.mkdtemp(prefix="civicsight_curl_")
    db_path = Path(td) / "curl_evidence.db"
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    env["PYTHONPATH"] = f"{PROJECT_ROOT}{os.pathsep}{BACKEND_DIR}"
    log_fh = open(Path(td) / "srv.log", "wb")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8769"],
        cwd=str(BACKEND_DIR),
        env=env,
        stdout=log_fh,
        stderr=subprocess.STDOUT,
    )
    try:
        for _ in range(60):
            r = subprocess.run(
                ["curl.exe", "-s", "-o", "NUL", "-w", "%{http_code}", "http://127.0.0.1:8769/health"],
                capture_output=True,
                text=True,
            )
            if r.stdout.strip() == "200":
                break
            time.sleep(0.3)

        def run_curl(label, args):
            r = subprocess.run(["curl.exe", "-s", "-i"] + args, capture_output=True, text=True)
            lines = r.stdout.splitlines()
            status_line = lines[0] if lines else ""
            body = r.stdout.split("\n\n", 1)[-1] if "\n\n" in r.stdout else r.stdout
            print(f"=== {label} ===")
            print(f"Status: {status_line}")
            display_body = body.strip()
            if '"access_token"' in display_body:
                parsed = json.loads(display_body)
                display_body = json.dumps({"token_type": parsed.get("token_type"), "user": parsed.get("user"), "access_token": "<REDACTED_JWT>"})
            print(f"Body: {display_body[:300]}")
            return status_line, body.strip()

        run_curl("GET /health", ["http://127.0.0.1:8769/health"])
        run_curl("GET /api/v1/reports (anonymous)", ["http://127.0.0.1:8769/api/v1/reports"])
        run_curl("GET /uploads/evidence/1/test.jpg (public blocked)", ["http://127.0.0.1:8769/uploads/evidence/1/test.jpg"])
        payload = json.dumps({"email": "officer1@civicsight.gov", "password": "Password123!"})
        _, login_body = run_curl(
            "POST /api/v1/auth/login (officer1)",
            ["-X", "POST", "http://127.0.0.1:8769/api/v1/auth/login", "-H", "Content-Type: application/json", "-d", payload],
        )
        tok = json.loads(login_body)["access_token"]
        run_curl("GET /api/v1/auth/me (authenticated)", ["-H", f"Authorization: Bearer {tok}", "http://127.0.0.1:8769/api/v1/auth/me"])
        run_curl("GET /api/v1/reports (officer authenticated)", ["-H", f"Authorization: Bearer {tok}", "http://127.0.0.1:8769/api/v1/reports"])
        run_curl(
            "POST /api/v1/auth/register (role escalation blocked)",
            [
                "-X", "POST", "http://127.0.0.1:8769/api/v1/auth/register",
                "-H", "Content-Type: application/json",
                "-d", json.dumps({"name": "Bad Actor", "email": "escalate@example.com", "password": "Password123!", "role": "Admin"}),
            ],
        )
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        log_fh.close()


if __name__ == "__main__":
    main()
