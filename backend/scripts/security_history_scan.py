"""Offline, redacted targeted secret scan over every reachable Git blob."""

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GIT = ["git", "-c", f"safe.directory={ROOT.as_posix()}"]
RULES = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "resend_key": re.compile(r"\bre_[A-Za-z0-9]{24,}\b"),
    "aws_access_key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "supabase_secret_key": re.compile(r"\bsb_secret_[A-Za-z0-9_-]{20,}\b"),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\b"),
    "credential_url": re.compile(
        r"(?:postgres(?:ql)?(?:\+asyncpg)?|https?)://[^\s:'\"]+:[^\s@'\"]+@[^\s'\"]+"
    ),
}


def main():
    blobs = subprocess.check_output(
        [*GIT, "rev-list", "--objects", "--all"], cwd=ROOT, text=True
    ).splitlines()
    process = subprocess.Popen(
        [*GIT, "cat-file", "--batch"], cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE
    )
    candidates = []
    scanned = skipped = total = 0
    for item in blobs:
        sha, _, path = item.partition(" ")
        process.stdin.write((sha + "\n").encode())
        process.stdin.flush()
        header = process.stdout.readline().decode().split()
        size = int(header[2])
        data = process.stdout.read(size)
        process.stdout.read(1)
        if header[1] != "blob":
            continue
        total += 1
        if size > 2_000_000 or b"\x00" in data:
            skipped += 1
            continue
        scanned += 1
        content = data.decode("utf-8", errors="replace")
        for kind, pattern in RULES.items():
            for match in pattern.finditer(content):
                value = match.group()
                disposition = "REVIEW"
                if kind == "credential_url" and any(
                    x in value.lower()
                    for x in [
                        "localhost",
                        "127.0.0.1",
                        "@db-host",
                        "@host",
                        "your_",
                        "<",
                        "{",
                        "example",
                    ]
                ):
                    disposition = "EXAMPLE_OR_LOCAL"
                if kind == "jwt":
                    import base64

                    try:
                        payload = value.split(".")[1]
                        claims = json.loads(
                            base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
                        )
                        disposition = (
                            "PUBLIC_ANON_KEY"
                            if claims.get("role") == "anon"
                            else "REVIEW_PRIVILEGED_TOKEN"
                        )
                    except (ValueError, KeyError):
                        pass
                candidates.append(
                    {
                        "blob": sha,
                        "path": path,
                        "line": content.count("\n", 0, match.start()) + 1,
                        "kind": kind,
                        "disposition": disposition,
                    }
                )
    process.stdin.close()
    process.wait()
    result = {
        "reachable_blobs": total,
        "text_blobs_scanned": scanned,
        "binary_or_large_blobs_not_scanned": skipped,
        "rules": list(RULES),
        "candidates": candidates,
        "limitation": "Targeted offline scan, not proof of secret absence; binary keystores and large build artifacts require separate review.",
    }
    (ROOT / "docs/security-audit/evidence/history-secrets.json").write_text(
        json.dumps(result, indent=2)
    )
    print(json.dumps({k: v for k, v in result.items() if k != "candidates"}))
    print(
        "Candidates",
        len(candidates),
        "requiring review",
        sum(c["disposition"].startswith("REVIEW") for c in candidates),
    )


if __name__ == "__main__":
    main()
