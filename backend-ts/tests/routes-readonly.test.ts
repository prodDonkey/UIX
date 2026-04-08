import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

import { parse } from "dotenv";

const projectEnvPath = path.resolve(process.cwd(), "../.env");
const hasProjectEnv = existsSync(projectEnvPath);
const projectEnv = hasProjectEnv ? parse(readFileSync(projectEnvPath, "utf8")) : {};

function ensureDbEnv() {
  const databaseUrl = process.env.DATABASE_URL ?? projectEnv.DATABASE_URL;
  if (!databaseUrl) {
    return false;
  }
  process.env.DATABASE_URL = databaseUrl;
  return true;
}

test("只读集成: scripts/scenes 路由可从真实数据库读取数据", { skip: !ensureDbEnv() }, async () => {
  const { createServer } = await import("../src/server.js");
  const app = createServer();
  try {
    const scriptsResponse = await app.inject({
      method: "GET",
      url: "/api/scripts"
    });
    assert.equal(scriptsResponse.statusCode, 200);
    const scripts = scriptsResponse.json() as Array<{ id: number; name: string }>;
    assert.equal(Array.isArray(scripts), true);

    const scenesResponse = await app.inject({
      method: "GET",
      url: "/api/scenes"
    });
    assert.equal(scenesResponse.statusCode, 200);
    const scenes = scenesResponse.json() as Array<{ id: number; name: string }>;
    assert.equal(Array.isArray(scenes), true);

    if (scripts.length > 0) {
      const detailResponse = await app.inject({
        method: "GET",
        url: `/api/scripts/${scripts[0].id}`
      });
      assert.equal(detailResponse.statusCode, 200);
      const detail = detailResponse.json() as { id: number; name: string };
      assert.equal(detail.id, scripts[0].id);
    }

    if (scenes.length > 0) {
      const detailResponse = await app.inject({
        method: "GET",
        url: `/api/scenes/${scenes[0].id}`
      });
      assert.equal(detailResponse.statusCode, 200);
      const detail = detailResponse.json() as { id: number; name: string; task_items: unknown[] };
      assert.equal(detail.id, scenes[0].id);
      assert.equal(Array.isArray(detail.task_items), true);
    }
  } finally {
    await app.close();
  }
});
