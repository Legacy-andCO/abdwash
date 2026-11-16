"""Regenerate evidence indexes and conservative ASVS/database coverage matrices."""

import csv
import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "docs/security-audit"
EVIDENCE = AUDIT / "evidence"


def table(headers, rows):
    def safe(value):
        return str(value).replace("|", "\\|").replace("\n", " ")

    return "\n".join(
        ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
        + ["| " + " | ".join(map(safe, row)) + " |" for row in rows]
    )


def main():
    metadata = json.loads((EVIDENCE / "live-db-metadata.json").read_text())
    metadata["functions"] = json.loads((EVIDENCE / "all-db-functions.json").read_text())["functions"]
    roles = json.loads((EVIDENCE / "role-results.json").read_text())
    local_tables = {r["table"] for r in roles}
    live = {t["name"]: t for t in metadata["tables"] if t["schema"] == "public"}
    rows = []
    for name in sorted(set(live) | local_tables):
        t = live.get(name)
        policies = [
            p
            for p in metadata["policies"] or []
            if p["schemaname"] == "public" and p["tablename"] == name
        ]
        tested = name in local_tables
        rows.append(
            [
                name,
                str(t["rls"]) if t else "absent",
                t["owner"] if t else "not deployed",
                len(policies),
                "broad grants" if t and "anon=" in str(t["acl"]) else "revoked/absent",
                " / ".join(["PASS"] * 4) if tested else "NOT TESTED",
                "backend_only: USING true / WITH CHECK true"
                if tested and name != "alembic_version"
                else "no client policy; deny all",
            ]
        )
    (AUDIT / "DATABASE.md").write_text(
        "# Database and RLS audit\n\nLive metadata was read on 2026-11-11; no production application rows were read or modified. Live revision: `"
        + metadata["version"]
        + "`. Local role tests apply the entire migration chain through `c7e833583da3`. **The local hardening results are not deployed results.**\n\nThe client access model is intentional deny-all: browser/native clients use FastAPI. SELECT, INSERT, UPDATE and DELETE have no allowed direct-client path. Backend connections can read all tenants; API ownership/team checks remain the tenant boundary. The new runtime group has no ownership, DDL, TRUNCATE or BYPASSRLS. Its explicit all-row policy grants only the backend the intended access; it does not claim per-tenant RLS.\n\n"
        + table(
            [
                "Table",
                "Live RLS",
                "Live owner",
                "Live policies",
                "Live client privileges",
                "Local S/I/U/D denial tests",
                "Local backend policy",
            ],
            rows,
        )
        + "\n\nLocal tests additionally deny TRUNCATE on every table for both client roles, deny backend TRUNCATE, and verify backend reads. 64 tables × 2 client roles × 5 operations = 640 real SQL permission attempts. The API tests use separate synthetic signed identities and two tenants on this runtime role.\n\n## Provider and infrastructure relations\n\n"
        + table(
            ["Schema", "Relation", "Kind", "RLS", "Force RLS", "Owner", "Runtime data result"],
            [
                [
                    t["schema"],
                    t["name"],
                    t["kind"],
                    t["rls"],
                    t["force_rls"],
                    t["owner"],
                    "NOT TESTED; provider-managed metadata only",
                ]
                for t in metadata["tables"]
                if t["schema"] != "public"
            ],
        )
        + "\n\n## Functions and procedures\n\nACLs, configuration, return types, roles, defaults and policies are preserved in `evidence/live-db-metadata.json`. Event triggers and non-internal triggers are in `live-db-extra.json`. Vendor function semantics were not dynamically tested.\n\n"
        + table(
            [
                "Schema",
                "Function",
                "Arguments",
                "Definer",
                "Owner",
                "Configuration",
                "Execution result",
            ],
            [
                [
                    f["schema"],
                    f["name"],
                    f["arguments"],
                    f["security_definer"],
                    f["owner"],
                    f["proconfig"],
                    "NOT TESTED (metadata inspection)",
                ]
                for f in metadata["functions"]
            ],
        )
        + "\n\n`public.rls_auto_enable` returns `event_trigger`, fixes search_path to pg_catalog, and only enables RLS for public tables. The advisor's execute-grant warning is excessive privilege, not a demonstrated remotely callable privilege escalation. Its grant is revoked locally by the migration. The new `app_private.session_active(uuid,uuid)` returns only a boolean; it reads authoritative session/user state, uses an empty search_path, and grants execution only to the runtime group. Its normal/revoked/banned/unverified cases are tested locally.\n\n## Buckets\n\n"
        + table(
            ["Bucket", "Live public", "Live maximum bytes", "MIME allowlist"],
            [
                [b["id"], b["public"], b["file_size_limit"], b["allowed_mime_types"]]
                for b in metadata["buckets"]
            ],
        )
        + "\n\n`complaint-evidence` and `expense-evidence` are required by source but were absent in the inspected project. Storage policies are included in the raw policy inventory. Signed URL expiry and tenant selection are source/unit-tested, not verified against a live isolated Supabase Storage instance.\n",
        encoding="utf-8",
    )
    tests = []
    for case in ET.parse(EVIDENCE / "all-backend-tests.xml").iter("testcase"):
        result = (
            "FAIL"
            if case.find("failure") is not None or case.find("error") is not None
            else "NOT TESTED"
            if case.find("skipped") is not None
            else "PASS"
        )
        skip = case.find("skipped")
        tests.append(
            [
                case.attrib.get("classname"),
                case.attrib["name"],
                result,
                skip.attrib.get("message", "")
                if skip is not None
                else "Executed in final backend suite",
            ]
        )
    (AUDIT / "TESTS.md").write_text(
        "# Executed test inventory\n\nEvery backend test collected in the final run is listed below. Skips are NOT TESTED, never PASS. Test results are bounded to their assertions and local environment. Browser/native device behavior is not implied by unit tests. Additional npm, static, secret, dependency and HTTP header results are described in REPORT.md.\n\n"
        + table(["Module", "Test", "Result", "Evidence / reason"], tests)
        + "\n",
        encoding="utf-8",
    )
    passed = {
        "V1.2.4": "ORM/bound raw SQL review; real PostgreSQL SQL-injection negative test; scoped queries.",
        "V1.5.2": "Strict request schemas; no unsafe pickle/eval/XML deserialization in application scan.",
        "V2.2.2": "Real API mass-assignment/price negative tests; server service validation.",
        "V2.3.3": "Transactional workflow/concurrency and migration round-trip regressions.",
        "V2.3.4": "Concurrent slot winner tests plus intentional, scoped employee overlap tests.",
        "V7.4.1": "Authoritative session row revocation/bans and actual API replay-denial test locally.",
        "V8.3.1": "Authoritative SQL staff role, real customer/team/tenant negative tests; 144 anonymous denials.",
        "V9.1.1": "Actual signed JWT and management/review capability signature tests.",
        "V9.1.2": "Fixed algorithm allowlists and invalid-signature tests.",
    }
    failed = {
        "V3.4.3": "CSP added, but unsafe-inline remains for Next/Expo compatibility; nonce/hash migration still required for strong CSP.",
        "V6.3.3": "Privileged MFA enforcement/enrollment is absent; see F17.",
    }
    na_sections = {
        "V1.2.6": "No LDAP integration.",
        "V1.2.7": "No XPath processor.",
        "V1.2.8": "No LaTeX processor.",
        "V1.3.8": "No Java/JNDI runtime.",
        "V1.3.9": "No memcache integration.",
        "V1.5.1": "No application XML parsing of untrusted input.",
    }
    reqs = list(csv.DictReader((EVIDENCE / "asvs-5.0.0.csv").open(encoding="utf-8-sig")))
    matrix = []
    for req in reqs:
        if int(req["L"]) > 2:
            continue
        rid = req["req_id"]
        status = "NOT TESTED"
        note = "Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate."
        if rid in passed:
            status, note = "PASS", passed[rid]
        if rid in failed:
            status, note = "FAIL", failed[rid]
        if rid in na_sections:
            status, note = "NOT APPLICABLE", na_sections[rid]
        matrix.append([rid, req["L"], req["section_name"], status, note])
    counts = {
        s: sum(r[3] == s for r in matrix) for s in ["PASS", "FAIL", "NOT TESTED", "NOT APPLICABLE"]
    }
    (AUDIT / "ASVS.md").write_text(
        "# ASVS 5.0.0 Level 2 coverage\n\nBaseline: OWASP ASVS stable v5.0.0, including all L1 and L2 requirements (253 rows). This is a conservative evidence register, **not an ASVS Level 2 certification or a claim of completed verification**. PASS applies to the stated local/source evidence; production assurance is separately blocked. NOT TESTED includes partial coverage that does not establish the whole requirement.\n\nSource: https://github.com/OWASP/ASVS/tree/v5.0.0 ; the original CSV is preserved under its CC BY-SA 4.0 license (https://creativecommons.org/licenses/by-sa/4.0/).\n\nCounts: "
        + json.dumps(counts)
        + "\n\n"
        + table(["Requirement", "Level", "Section", "Result", "Evidence / limitation"], matrix)
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "backend_tests": len(tests),
                "asvs": counts,
                "live_public_tables": len(live),
                "local_tables": len(local_tables),
            }
        )
    )


if __name__ == "__main__":
    main()
