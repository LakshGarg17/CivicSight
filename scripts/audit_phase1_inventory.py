"""Phase 1 Inventory and Evidence Extraction Script.
Checks code files, OpenAPI endpoints, frontend routes, and environment variable references.
"""
import inspect as py_inspect
import json
import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path("d:/Projects/CivicSight").resolve()
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(BACKEND_DIR))

# 1. Inspect OpenAPI endpoints
from app.main import app

openapi_routes = []
for route in app.routes:
    if hasattr(route, "methods") and hasattr(route, "path"):
        methods = sorted(list(route.methods - {"HEAD", "OPTIONS"}))
        if methods:
            openapi_routes.append({"path": route.path, "methods": methods, "name": getattr(route, "name", "")})

openapi_routes.sort(key=lambda x: x["path"])

# 2. Inspect Environment Variables in code
env_vars_found = {}
pattern_os = re.compile(r'os\.(?:environ\.get|getenv)\s*\(\s*["\']([A-Z0-9_]+)["\']')
pattern_settings = re.compile(r'settings\.([A-Z0-9_]+)')
pattern_fe = re.compile(r'(?:process\.env|import\.meta\.env)\.([A-Z0-9_]+)')

for root, dirs, files in os.walk(PROJECT_ROOT):
    dirs[:] = [d for d in dirs if d not in {".git", ".venv", "node_modules", "Dataset", "runs", "__pycache__"}]
    for f in files:
        if f.endswith((".py", ".js", ".html", ".css", ".ts")):
            fp = Path(root) / f
            try:
                content = fp.read_text(encoding="utf-8", errors="ignore")
                for m in pattern_os.finditer(content):
                    var = m.group(1)
                    env_vars_found.setdefault(var, []).append(str(fp.relative_to(PROJECT_ROOT)))
                for m in pattern_settings.finditer(content):
                    var = m.group(1)
                    env_vars_found.setdefault(var, []).append(str(fp.relative_to(PROJECT_ROOT)))
                for m in pattern_fe.finditer(content):
                    var = m.group(1)
                    env_vars_found.setdefault(var, []).append(str(fp.relative_to(PROJECT_ROOT)))
            except Exception:
                pass

# Compare with .env.example
env_example_path = BACKEND_DIR / ".env.example"
example_vars = set()
if env_example_path.is_file():
    for line in env_example_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            example_vars.add(line.split("=", 1)[0].strip())

# 3. Frontend routes (HTML files and JS navigation links)
frontend_pages = []
for p in (PROJECT_ROOT / "frontend").glob("**/*.html"):
    frontend_pages.append(str(p.relative_to(PROJECT_ROOT)))

output_data = {
    "openapi_endpoints_count": len(openapi_routes),
    "openapi_routes": openapi_routes,
    "frontend_pages": sorted(frontend_pages),
    "env_vars_in_code": {k: sorted(list(set(v))) for k, v in sorted(env_vars_found.items())},
    "example_vars": sorted(list(example_vars)),
    "unaccounted_env_vars": sorted(list(set(env_vars_found.keys()) - example_vars)),
}

out_file = PROJECT_ROOT / "scratch" / "phase1_inventory_raw.json"
out_file.parent.mkdir(parents=True, exist_ok=True)
out_file.write_text(json.dumps(output_data, indent=2), encoding="utf-8")
print(f"Extracted {len(openapi_routes)} OpenAPI routes and {len(frontend_pages)} frontend pages.")
print(f"Saved inventory raw data to {out_file}")
