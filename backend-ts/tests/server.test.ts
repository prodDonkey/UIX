import test from "node:test";
import assert from "node:assert/strict";

test("health route 返回迁移状态", async () => {
  process.env.DATABASE_URL = process.env.DATABASE_URL ?? "mysql://test:test@127.0.0.1:3306/test";
  const { createServer } = await import("../src/server.js");
  const app = createServer();
  try {
    const response = await app.inject({
      method: "GET",
      url: "/health"
    });
    assert.equal(response.statusCode, 200);
    const payload = response.json() as {
      ok: boolean;
      migration: { backend: string; phase: string };
    };
    assert.equal(payload.ok, true);
    assert.equal(payload.migration.backend, "typescript");
    assert.equal(payload.migration.phase, "dual-run");
  } finally {
    await app.close();
  }
});
