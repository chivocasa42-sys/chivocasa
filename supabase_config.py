"""Supabase settings shared by the Python scripts.

Local runs read .env.local / .env at the repo root; these files win over
machine-wide environment variables, which may belong to another project.
CI has no such files and uses the SUPABASE_URL / SUPABASE_SERVICE_KEY secrets.
Never hardcode keys here: the service role key bypasses row-level security.
"""

import base64
import json
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent


def _load_env_file(path):
    """Load KEY=VALUE lines from path into os.environ, overriding existing values."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip().removeprefix("export ").strip()
        os.environ[name] = value.strip().strip('"').strip("'")


def _jwt_project_ref(key):
    """Return the project ref embedded in a legacy JWT API key, or None."""
    try:
        payload = key.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))).get("ref")
    except (IndexError, ValueError, AttributeError):
        return None


for _env_file in (".env", ".env.local"):  # later files win
    _load_env_file(_REPO_ROOT / _env_file)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print("Warning: SUPABASE_URL / SUPABASE_SERVICE_KEY not set; add them to .env.local", file=sys.stderr)

_key_ref = _jwt_project_ref(SUPABASE_SERVICE_KEY)
if _key_ref and SUPABASE_URL and f"//{_key_ref}." not in SUPABASE_URL:
    raise RuntimeError(f"SUPABASE_SERVICE_KEY belongs to project '{_key_ref}' but SUPABASE_URL is {SUPABASE_URL}")
