import test from "node:test";
import assert from "node:assert/strict";

import {
  compileSceneScript,
  dumpTaskSnapshot,
  loadTaskSnapshot,
  mergeTaskVariableMeta,
  parseScriptTasks,
  taskSnapshotVariableMeta
} from "../src/services/scene-compiler.js";

test("parseScriptTasks 下沉脚本级 interface 到 task 快照", () => {
  const content = `
interface:
  method: POST
  url: https://example.com
tasks:
  - name: 下单
    flow: []
`;

  const tasks = parseScriptTasks(content);
  assert.equal(tasks.length, 1);
  assert.deepEqual(tasks[0].task.interface, {
    method: "POST",
    url: "https://example.com"
  });
});

test("mergeTaskVariableMeta 保留并覆盖输入输出变量", () => {
  const snapshot = dumpTaskSnapshot({
    name: "分配",
    flow: [],
    sceneVariables: {
      inputs: [{ target_path: "interface.body.uid", expression: "${uid}" }],
      outputs: [{ name: "orderNo", source_path: "respMsg.data.orderNo" }]
    }
  });

  const merged = mergeTaskVariableMeta(loadTaskSnapshot(snapshot), {
    inputBindings: [{ target_path: "interface.body.uid", expression: "${nextUid}" }],
    outputVariables: [{ name: "recycleOrderId", source_path: "respMsg.data.fields.recycleOrderId" }]
  });

  const meta = taskSnapshotVariableMeta(dumpTaskSnapshot(merged));
  assert.deepEqual(meta.inputs, [{ target_path: "interface.body.uid", expression: "${nextUid}" }]);
  assert.deepEqual(meta.outputs, [
    { name: "orderNo", source_path: "respMsg.data.orderNo" },
    { name: "recycleOrderId", source_path: "respMsg.data.fields.recycleOrderId" }
  ]);
});

test("compileSceneScript 禁止引用未定义前序变量", () => {
  const first = dumpTaskSnapshot({
    name: "下单",
    flow: [],
    sceneVariables: {
      inputs: [{ target_path: "interface.body.uid", expression: "${uid}" }]
    }
  });

  assert.throws(() => compileSceneScript({}, [first]), {
    name: "Error",
    message: "第 1 个任务引用了未定义变量：uid。只能引用前序任务输出变量"
  });
});
