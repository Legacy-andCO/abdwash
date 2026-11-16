"""Offline comparison against a downloaded PyPA advisory-database ZIP.

Usage: python scripts/security_python_audit.py <zip> <output.json>
No network calls and no dependency metadata is transmitted.
"""

import hashlib
import importlib.metadata as metadata
import json
import sys
import zipfile
from pathlib import Path

import yaml
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version


def main():
    archive, output = map(Path, sys.argv[1:3])
    installed = {
        canonicalize_name(d.metadata["Name"]): d.version
        for d in metadata.distributions()
        if d.metadata.get("Name")
    }
    findings = []
    count = 0
    with zipfile.ZipFile(archive) as database:
        for name in database.namelist():
            if "/vulns/" not in name or not name.endswith(".yaml"):
                continue
            advisory = yaml.safe_load(database.read(name))
            count += 1
            if advisory.get("withdrawn"):
                continue
            for item in advisory.get("affected", []):
                package = canonicalize_name(item.get("package", {}).get("name", ""))
                if package not in installed:
                    continue
                try:
                    version = Version(installed[package])
                except InvalidVersion:
                    continue
                affected = installed[package] in item.get("versions", [])
                for interval in item.get("ranges", []):
                    if interval.get("type") != "ECOSYSTEM":
                        continue
                    active = False
                    for event in interval.get("events", []):
                        if "introduced" in event and (
                            event["introduced"] == "0" or version >= Version(event["introduced"])
                        ):
                            active = True
                        if "fixed" in event and version >= Version(event["fixed"]):
                            active = False
                        if "last_affected" in event and version > Version(event["last_affected"]):
                            active = False
                    affected |= active
                if affected:
                    findings.append(
                        {
                            "package": package,
                            "version": installed[package],
                            "id": advisory["id"],
                            "aliases": advisory.get("aliases", []),
                            "details": advisory.get("details", ""),
                            "references": advisory.get("references", []),
                            "affected": item,
                        }
                    )
    result = {
        "source": "https://github.com/pypa/advisory-database",
        "retrieved": "2026-11-11",
        "database_sha256": hashlib.file_digest(archive.open("rb"), "sha256").hexdigest(),
        "advisories_scanned": count,
        "installed_packages": installed,
        "findings": findings,
        "limitation": "Offline PyPA database comparison; no inventory transmitted. This is not pip-audit and advisory coverage is limited to this source.",
    }
    output.write_text(json.dumps(result, indent=2))
    print(json.dumps({"advisories": count, "packages": len(installed), "findings": len(findings)}))


if __name__ == "__main__":
    main()
