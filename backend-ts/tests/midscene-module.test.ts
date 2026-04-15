import test from "node:test";
import assert from "node:assert/strict";

import { executeSceneAndroidYaml } from "../src/modules/midscene/android-executor.js";
import { executeCompiledScene } from "../src/modules/midscene/scene-executor.js";

const ENV_KEYS = [
  "MIDSCENE_MODEL_NAME",
  "MIDSCENE_MODEL_BASE_URL",
  "MIDSCENE_MODEL_API_KEY",
  "MIDSCENE_MODEL_FAMILY"
] as const;

function withMidsceneEnv() {
  const snapshot = new Map<string, string | undefined>();
  for (const key of ENV_KEYS) {
    snapshot.set(key, process.env[key]);
    process.env[key] = {
      MIDSCENE_MODEL_NAME: "qwen-vl-max",
      MIDSCENE_MODEL_BASE_URL: "https://example.test/v1",
      MIDSCENE_MODEL_API_KEY: "demo-key",
      MIDSCENE_MODEL_FAMILY: "qwen3-vl"
    }[key];
  }

  return () => {
    for (const key of ENV_KEYS) {
      const value = snapshot.get(key);
      if (value === undefined) {
        delete process.env[key];
      } else {
        process.env[key] = value;
      }
    }
  };
}

test("executeSceneAndroidYaml 使用默认设备并返回 Midscene 结果", async () => {
  const restore = withMidsceneEnv();
  try {
    const calls: string[] = [];
    const result = await executeSceneAndroidYaml(
      {
        yamlContent: `android:
  deviceId: ""
tasks:
  - name: 前往服务
    flow:
      - aiAction: 点击前往服务按钮
  - name: 点击预约点签到
    flow:
      - aiAssert: 出现输入手机尾号页面
`,
        defaultDeviceId: "emulator-5554"
      },
      {
        createAgent: async (deviceId?: string) => {
          calls.push(deviceId ?? "");
          return {
            async runYaml() {
              return {
                result: {
                  0: "ok",
                  1: "done"
                }
              };
            },
            async destroy() {
              calls.push("destroyed");
            }
          };
        }
      }
    );

    assert.deepEqual(calls, ["emulator-5554", "destroyed"]);
    assert.equal(result.success, true);
    assert.deepEqual(result.outputs, { 0: "ok", 1: "done" });
    assert.deepEqual(
      result.task_results.map((item) => item.task_name),
      ["前往服务", "点击预约点签到"]
    );
  } finally {
    restore();
  }
});

test("executeSceneAndroidYaml 在非 android YAML 上报错", async () => {
  const restore = withMidsceneEnv();
  try {
    await assert.rejects(
      () =>
        executeSceneAndroidYaml({
          yamlContent: `tasks:
  - name: only-http
    flow: []
`
        }),
      /缺少 android 配置/
    );
  } finally {
    restore();
  }
});

test("executeCompiledScene 命中 android 场景时走 Midscene 模块", async () => {
  const result = await executeCompiledScene(
    {
      compiledYaml: `android:
  deviceId: ""
tasks:
  - name: 打款
    flow:
      - aiAction: 点击确认打款
`,
      taskSnapshots: ["ignored"],
      httpTimeoutSec: 30,
      defaultAndroidDeviceId: "device-1"
    },
    {
      executeAndroid: async (params) => ({
        success: true,
        message: params.defaultDeviceId ?? "",
        outputs: { platform: "android" },
        task_results: [{ task_name: "打款", ok: true }],
        result: { platform: "android" }
      }),
      executeHttp: async () => {
        throw new Error("should not hit http executor");
      }
    }
  );

  assert.equal(result.message, "device-1");
  assert.deepEqual(result.outputs, { platform: "android" });
});
