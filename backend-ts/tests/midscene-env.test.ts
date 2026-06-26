import test from "node:test";
import assert from "node:assert/strict";

import { executeSceneAndroidYaml } from "../src/modules/midscene/android-executor.js";

const ENV_KEYS = [
  "MIDSCENE_MODEL_NAME",
  "MIDSCENE_MODEL_BASE_URL",
  "MIDSCENE_MODEL_API_KEY",
  "MIDSCENE_MODEL_FAMILY",
  "LLM_MODEL_NAME",
  "LLM_BASE_URL",
  "LLM_API_KEY",
  "LLM_MODEL_FAMILY"
] as const;

test("executeSceneAndroidYaml 支持从 LLM 环境变量回填 Midscene 配置", async () => {
  const snapshot = new Map<string, string | undefined>();
  for (const key of ENV_KEYS) {
    snapshot.set(key, process.env[key]);
    delete process.env[key];
  }

  process.env.LLM_MODEL_NAME = "qwen-vl-max";
  process.env.LLM_BASE_URL = "https://example.test/v1";
  process.env.LLM_API_KEY = "demo-key";
  process.env.LLM_MODEL_FAMILY = "qwen3-vl";

  try {
    await executeSceneAndroidYaml(
      {
        yamlContent: `android:
  deviceId: ""
tasks:
  - name: smoke
    flow:
      - aiAction: 点击按钮
`
      },
      {
        createAgent: async () => ({
          async runYaml() {
            return { result: { ok: true } };
          },
          async destroy() {}
        })
      }
    );

    assert.equal(process.env.MIDSCENE_MODEL_NAME, "qwen-vl-max");
    assert.equal(process.env.MIDSCENE_MODEL_BASE_URL, "https://example.test/v1");
    assert.equal(process.env.MIDSCENE_MODEL_API_KEY, "demo-key");
    assert.equal(process.env.MIDSCENE_MODEL_FAMILY, "qwen3-vl");
  } finally {
    for (const key of ENV_KEYS) {
      const value = snapshot.get(key);
      if (value === undefined) {
        delete process.env[key];
      } else {
        process.env[key] = value;
      }
    }
  }
});
