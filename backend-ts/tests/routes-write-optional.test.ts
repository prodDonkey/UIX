import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

import { parse } from "dotenv";

const backendEnvPath = path.resolve(process.cwd(), "../backend/.env");
const hasBackendEnv = existsSync(backendEnvPath);
const backendEnv = hasBackendEnv ? parse(readFileSync(backendEnvPath, "utf8")) : {};

function ensureDbEnv() {
  const databaseUrl = process.env.DATABASE_URL ?? backendEnv.DATABASE_URL;
  if (!databaseUrl) {
    return false;
  }
  process.env.DATABASE_URL = databaseUrl;
  return true;
}

const shouldRunWriteTests = process.env.UIX_ENABLE_DB_WRITE_TESTS === "1" && ensureDbEnv();

test("可选写集成: scripts 创建复制删除并清理", { skip: !shouldRunWriteTests }, async () => {
  const { createServer } = await import("../src/server.js");
  const app = createServer();
  const createdIds: number[] = [];

  try {
    const createResponse = await app.inject({
      method: "POST",
      url: "/api/scripts",
      payload: {
        name: `ts-write-test-${Date.now()}`,
        content: "tasks:\n  - name: smoke\n    flow: []\n",
        source_type: "manual"
      }
    });
    assert.equal(createResponse.statusCode, 201);
    const created = createResponse.json() as { id: number; name: string };
    createdIds.push(created.id);
    assert.match(created.name, /^ts-write-test-/);

    const copyResponse = await app.inject({
      method: "POST",
      url: `/api/scripts/${created.id}/copy`
    });
    assert.equal(copyResponse.statusCode, 201);
    const copied = copyResponse.json() as { id: number; name: string };
    createdIds.push(copied.id);
    assert.equal(copied.name, `${created.name}-copy`);
  } finally {
    for (const id of createdIds.reverse()) {
      await app.inject({
        method: "DELETE",
        url: `/api/scripts/${id}`
      });
    }
    await app.close();
  }
});
