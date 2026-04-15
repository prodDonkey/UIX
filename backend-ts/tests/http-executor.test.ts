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
            uid: "${missingUid}",
            addressId: "${missingAddressId}"
          }
        }
      })
    ],
    timeoutSec: 5
  });

  assert.equal(result.success, false);
  assert.equal(result.task_results[0]?.error, "缺少执行变量：missingAddressId, missingUid");
});

test("executeSceneHttpTasks 在 Cookie 失效时返回明确错误", async () => {
  process.env.DATABASE_URL = process.env.DATABASE_URL ?? "mysql://test:test@127.0.0.1:3306/test";
  const { executeSceneHttpTasks } = await import("../src/services/http-executor.js");
  const fetchMock = mock.method(globalThis, "fetch", async () => {
    return new Response(
      JSON.stringify({
        status: -3,
        desc: "调用接口错误",
        data: null
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
            body: {}
          }
        })
      ],
      timeoutSec: 5
    });

    assert.equal(result.success, false);
    assert.equal(result.task_results[0]?.error, "接口调用失败：调用接口错误，可能是 Cookie 已失效，需要重新登录");
  } finally {
    fetchMock.mock.restore();
  }
});

test("executeSceneHttpTasks 在接口业务失败时返回明确错误", async () => {
  process.env.DATABASE_URL = process.env.DATABASE_URL ?? "mysql://test:test@127.0.0.1:3306/test";
  const { executeSceneHttpTasks } = await import("../src/services/http-executor.js");
  const fetchMock = mock.method(globalThis, "fetch", async () => {
    return new Response(
      JSON.stringify({
        respCode: 0,
        respMsg: JSON.stringify({
          code: -111,
          errorMsg: "请选择上门时间",
          raw: false
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
            body: {}
          }
        })
      ],
      timeoutSec: 5
    });

    assert.equal(result.success, false);
    assert.equal(result.task_results[0]?.error, "接口业务失败：请选择上门时间");
  } finally {
    fetchMock.mock.restore();
  }
});
