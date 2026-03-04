import assert from "node:assert/strict";
import test from "node:test";
import { RunManager, RunStateError } from "./run-manager.js";

test("createRun initializes queued run", () => {
  const manager = new RunManager();
  const run = manager.createRun({
    runId: 101,
    yamlContent: "android: {}"
  });

  assert.equal(run.runId, 101);
  assert.equal(run.status, "queued");
  assert.equal(run.currentTask, null);
  assert.equal(run.completed, 0);
});

test("startRun transitions queued -> running and is idempotent", () => {
  const manager = new RunManager();
  manager.createRun({
    runId: 102,
    yamlContent: "android: {}"
  });

  const first = manager.startRun(102);
  const second = manager.startRun(102);

  assert.equal(first.status, "running");
  assert.equal(second.status, "running");
  assert.ok(first.startedAt);
  assert.ok(second.startedAt);
});

test("updateProgress updates progress fields", () => {
  const manager = new RunManager();
  manager.createRun({
    runId: 103,
    yamlContent: "android: {}"
  });

  const updated = manager.updateProgress(103, {
    currentTask: "登录流程",
    currentAction: "aiTap 登录按钮",
    completed: 2,
    total: 5
  });

  assert.equal(updated.status, "running");
  assert.equal(updated.currentTask, "登录流程");
  assert.equal(updated.currentAction, "aiTap 登录按钮");
  assert.equal(updated.completed, 2);
  assert.equal(updated.total, 5);
});

test("cancelRun is idempotent", () => {
  const manager = new RunManager();
  manager.createRun({
    runId: 104,
    yamlContent: "android: {}"
  });
  manager.startRun(104);

  const first = manager.cancelRun(104);
  const second = manager.cancelRun(104);

  assert.equal(first.status, "cancelled");
  assert.equal(second.status, "cancelled");
});

test("cannot create duplicated active run", () => {
  const manager = new RunManager();
  manager.createRun({
    runId: 105,
    yamlContent: "android: {}"
  });

  assert.throws(
    () =>
      manager.createRun({
        runId: 105,
        yamlContent: "android: {}"
      }),
    (error: unknown) =>
      error instanceof RunStateError && error.code === "RUN_ALREADY_ACTIVE"
  );
});

test("terminal run rejects invalid transition", () => {
  const manager = new RunManager();
  manager.createRun({
    runId: 106,
    yamlContent: "android: {}"
  });
  manager.startRun(106);
  manager.markSuccess(106);

  assert.throws(
    () => manager.cancelRun(106),
    (error: unknown) =>
      error instanceof RunStateError && error.code === "RUN_TERMINAL"
  );
});
