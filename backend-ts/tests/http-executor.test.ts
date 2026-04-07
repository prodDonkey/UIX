import test, { mock } from "node:test";
import assert from "node:assert/strict";

import { dumpTaskSnapshot } from "../src/services/scene-compiler.js";

test("executeSceneHttpTasks 支持字符串 respMsg 提取与数组路径绑定", async () => {
  process.env.DATABASE_URL = process.env.DATABASE_URL ?? "mysql://test:test@127.0.0.1:3306/test";
  const { executeSceneHttpTasks } = await import("../src/services/http-executor.js");
  const fetchMock = mock.method(globalThis, "fetch", async (input: string | URL | Request, init?: RequestInit) => {
    const request = input instanceof Request ? input : new Request(input, init);
    const payload = JSON.parse(await request.text()) as {
      params: Array<{ value: string }>;
    };
    assert.equal(payload.params[1]?.value, "1965240793320916565");
    return new Response(
      JSON.stringify({
        respCode: 0,
        respMsg: JSON.stringify({
          code: 0,
          data: {
            fields: {
              recycleOrderId: "2041446776720392222"
            }
          }
        })
      }),
      {
        status: 200,
        headers: {
          "content-type": "application/json"
        }
      }
    );
  });

  try {
    const result = await executeSceneHttpTasks({
      taskSnapshots: [
        dumpTaskSnapshot({
          name: "下单",
          flow: [],
          interface: {
            method: "POST",
            url: "https://example.com/api/basicdata/getresult",
            contentType: "application/json",
            body: {
              params: [{ value: "keep" }, { value: "" }]
            }
          },
          sceneVariables: {
            inputs: [{ target_path: "interface.body.params[1].value", expression: "1965240793320916565" }],
            outputs: [{ name: "recycleOrderId", source_path: "respMsg.data.fields.recycleOrderId" }]
          }
        })
      ],
      timeoutSec: 5
    });

    assert.equal(result.success, true);
    assert.deepEqual(result.outputs, {
      recycleOrderId: "2041446776720392222"
    });
  } finally {
    fetchMock.mock.restore();
  }
});

test("executeSceneHttpTasks 在缺少变量时返回准确错误", async () => {
  process.env.DATABASE_URL = process.env.DATABASE_URL ?? "mysql://test:test@127.0.0.1:3306/test";
  const { executeSceneHttpTasks } = await import("../src/services/http-executor.js");
  const result = await executeSceneHttpTasks({
    taskSnapshots: [
      dumpTaskSnapshot({
        name: "下单",
        flow: [],
        interface: {
          method: "POST",
          url: "https://example.com/api/basicdata/getresult",
          contentType: "application/json",
          body: {
            uid: "${uid}",
            addressId: "${addressId}"
          }
        }
      })
    ],
    timeoutSec: 5
  });

  assert.equal(result.success, false);
  assert.equal(result.task_results[0]?.error, "缺少执行变量：addressId, uid");
});
