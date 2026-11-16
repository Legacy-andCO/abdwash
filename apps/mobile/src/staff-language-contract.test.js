import { it, expect } from "vitest";
import { readdirSync, readFileSync } from "node:fs";
import ts from "typescript";
import { staffArabic } from "./staff-translations";
  it("provides Arabic for every static staff translation call", () => {
    const root = new URL("./", import.meta.url);
    const missing = new Set();
    for (const path of readdirSync(root, { recursive: true }).map(String)) {
      if (!/\.(ts|tsx)$/.test(path) || path.includes(".test.")) continue;
      const source = readFileSync(new URL(path.replaceAll("\\", "/"), root), "utf8");
      const file = ts.createSourceFile(path, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
      function visit(node) {
        if (ts.isCallExpression(node) && node.expression.getText(file) === "t") {
          const key = node.arguments[0];
          if (key && ts.isStringLiteral(key) && !staffArabic[key.text]) missing.add(key.text);
        }
        ts.forEachChild(node, visit);
      }
      visit(file);
    }
    expect([...missing]).toEqual([]);
  });
