"""Read-only, redacted audit inventory. Never connects to a database."""

import ast
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/security-audit/evidence"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    routes = []
    for path in sorted((ROOT / "backend/app/api").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        prefixes = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                if ast.unparse(node.value.func) == "APIRouter":
                    prefixes.update(
                        {
                            ast.unparse(t): next(
                                (
                                    ast.literal_eval(k.value)
                                    for k in node.value.keywords
                                    if k.arg == "prefix"
                                ),
                                "",
                            )
                            for t in node.targets
                        }
                    )
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in node.decorator_list:
                if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Attribute):
                    continue
                if dec.func.attr not in {"get", "post", "put", "patch", "delete", "options"}:
                    continue
                annotations = [ast.unparse(a.annotation) for a in node.args.args if a.annotation]
                auth = "PUBLIC"
                for marker, label in [
                    ("optional_identity", "OPTIONAL JWT"),
                    ("IdentityDep", "CUSTOMER JWT"),
                    ("required_identity", "CUSTOMER JWT"),
                    ("StaffDep", "STAFF"),
                    ("Staff", "STAFF"),
                    ("staff_context", "STAFF"),
                    ("ManagerContext", "MANAGER/ADMIN"),
                    ("AdminContext", "ADMIN"),
                ]:
                    if any(marker == a or marker in a for a in annotations):
                        auth = label
                params = ast.unparse(node.args)
                if "management_token" in params:
                    auth += " + BOOKING CAPABILITY"
                if "supplied_secret" in params:
                    auth = "DISPATCH SECRET"
                routes.append(
                    dict(
                        method=dec.func.attr.upper(),
                        path=prefixes.get(ast.unparse(dec.func.value), "")
                        + ast.literal_eval(dec.args[0]),
                        function=node.name,
                        source=str(path.relative_to(ROOT)).replace("\\", "/"),
                        line=node.lineno,
                        authentication=auth,
                        parameters=params,
                        status="NOT TESTED",
                    )
                )
    (OUT / "endpoints.json").write_text(json.dumps(routes, indent=2), encoding="utf-8")
    headers = ["Method", "Path", "Authentication boundary", "Source", "Dynamic result"]
    lines = [
        "# Endpoint inventory",
        "",
        "Generated from Python AST; boundary labels require service-level ownership checks. NOT TESTED means no endpoint-specific runtime claim.",
        "",
        "| " + " | ".join(headers) + " |",
        "|---|---|---|---|---|",
    ]
    anonymous = (
        {
            (r["method"], r["path"]): r
            for r in json.loads((OUT / "endpoint-anonymous-results.json").read_text())
        }
        if (OUT / "endpoint-anonymous-results.json").exists()
        else {}
    )
    lines += [
        f"| {r['method']} | `{r['path']}` | {r['authentication']} | `{r['source']}:{r['line']}` | {'PASS: anonymous denied; authorized/object cases NOT TESTED individually' if (r['method'], r['path']) in anonymous and anonymous[(r['method'], r['path'])]['result'] == 'PASS' else 'NOT TESTED individually (see test inventory)'} |"
        for r in routes
    ]
    (OUT.parent / "ENDPOINTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    files = subprocess.check_output(
        ["git", "-c", f"safe.directory={ROOT.as_posix()}", "ls-files"], cwd=ROOT, text=True
    ).splitlines()
    (OUT / "tracked-files.json").write_text(json.dumps(files, indent=2), encoding="utf-8")
    print(json.dumps({"routes": len(routes), "tracked_files": len(files)}))


if __name__ == "__main__":
    main()
