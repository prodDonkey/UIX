import assert from "node:assert/strict";
import test from "node:test";
import { buildProgressFromDump, YamlRunner } from "./yaml-runner.js";

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
