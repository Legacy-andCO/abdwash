"""Prepare the expiring, fixed-project operator without exporting service keys."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

root = Path(__file__).resolve().parents[2]
secrets = json.loads((root / "tmp/security-staging.json").read_text())
if secrets["project_ref"] != "mgfzfgvlrxwyyftwukwf":
    raise SystemExit("Only isolated staging is permitted")
if secrets.get("operator_disabled"):
    raise SystemExit("The staging operator is retired; no active operator credential exists.")
source = (Path(__file__).parent / "staging_operator.ts").read_text()
source = source.replace(
    "__TOKEN_HASH__", hashlib.sha256(secrets["operator_token"].encode()).hexdigest()
)
source = source.replace("__EXPIRES__", (datetime.now(UTC) + timedelta(hours=1)).isoformat())
(root / "tmp/staging_operator.ts").write_text(source, encoding="utf-8")
print("Prepared fixed staging operator (one-hour maximum lifetime); credentials remain ignored.")
