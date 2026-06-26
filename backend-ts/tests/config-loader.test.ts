import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

import { loadEnvFiles } from "../src/config-loader.js";

test("loadEnvFiles 支持回退读取仓库根 .env，且 backend-ts/.env 优先", () => {
  const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), "uix-config-loader-"));
  const repoRoot = path.join(tempRoot, "repo");
  const backendTsRoot = path.join(repoRoot, "backend-ts");

  fs.mkdirSync(backendTsRoot, { recursive: true });
  fs.writeFileSync(path.join(repoRoot, ".env"), "ROOT_ONLY=root-value\nSHARED=from-root\n", "utf8");
  fs.writeFileSync(path.join(backendTsRoot, ".env"), "BACKEND_ONLY=backend-value\nSHARED=from-backend\n", "utf8");

  const keys = ["ROOT_ONLY", "BACKEND_ONLY", "SHARED"] as const;
  const snapshot = new Map<string, string | undefined>();
  for (const key of keys) {
    snapshot.set(key, process.env[key]);
    delete process.env[key];
  }

  try {
    loadEnvFiles(backendTsRoot);

    assert.equal(process.env.ROOT_ONLY, "root-value");
    assert.equal(process.env.BACKEND_ONLY, "backend-value");
    assert.equal(process.env.SHARED, "from-backend");
  } finally {
    for (const key of keys) {
      const value = snapshot.get(key);
      if (value === undefined) {
        delete process.env[key];
      } else {
        process.env[key] = value;
      }
    }

    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});
