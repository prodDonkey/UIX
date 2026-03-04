import assert from "node:assert/strict";
import test from "node:test";
import {
  buildProgressFromDump,
  normalizeUserFacingErrorMessage,
  resolveTargetDeviceId,
  YamlRunner
} from "./yaml-runner.js";

test("buildProgressFromDump computes running step and progress", () => {
  const dump = {
    tasks: [
      { status: "finished", subType: "打开应用" },
      { status: "running", param: { name: "输入账号" } },
      { status: "queued", thought: "点击登录" }
    ]
  } as any;

  const progress = buildProgressFromDump(dump);
  assert.equal(progress.total, 3);
  assert.equal(progress.completed, 1);
  assert.equal(progress.currentTask, "输入账号");
  assert.equal(progress.currentAction, "输入账号");
  assert.equal(progress.executionDump, dump);
});

test("buildProgressFromDump counts failed/cancelled as completed", () => {
  const dump = {
    tasks: [
      { status: "failed", type: "aiAction" },
      { status: "cancelled", subType: "回到首页" }
    ]
  } as any;

  const progress = buildProgressFromDump(dump);
  assert.equal(progress.total, 2);
  assert.equal(progress.completed, 2);
  assert.equal(progress.currentTask, "回到首页");
});

test("cancelRun returns false when run handle is missing", async () => {
  const runner = new YamlRunner();
  const cancelled = await runner.cancelRun(9999);
  assert.equal(cancelled, false);
});

test("resolveTargetDeviceId prefers payload value", () => {
  const resolved = resolveTargetDeviceId("emulator-5554", "device-from-yaml");
  assert.equal(resolved, "emulator-5554");
});

test("resolveTargetDeviceId falls back to yaml value", () => {
  const resolved = resolveTargetDeviceId("", "device-from-yaml");
  assert.equal(resolved, "device-from-yaml");
});

test("resolveTargetDeviceId returns undefined when both missing", () => {
  const resolved = resolveTargetDeviceId(undefined, " ");
  assert.equal(resolved, undefined);
});

test("normalizeUserFacingErrorMessage maps free-tier exhausted to Chinese hint", () => {
  const raw =
    'AI call error: failed to call AI model service (qwen3.5-plus): 403 The free tier of the model has been exhausted.';
  const message = normalizeUserFacingErrorMessage(raw);
  assert.equal(
    message,
    "模型调用失败：当前模型免费额度已用尽（403）。请在模型平台关闭“仅免费额度”限制或充值后重试。"
  );
});

test("normalizeUserFacingErrorMessage trims stack trace", () => {
  const raw = "waitFor timeout: 登录页面未出现 at ScriptPlayer.run (/x/y/z.ts:1:1)";
  const message = normalizeUserFacingErrorMessage(raw);
  assert.equal(message, "waitFor timeout: 登录页面未出现");
});
