import test from "node:test";
import assert from "node:assert/strict";

import { ensureAdbConnected, isNetworkAdbAddress } from "../src/modules/midscene/adb-connect.js";

test("isNetworkAdbAddress 仅识别 host:port 形态", () => {
  assert.equal(isNetworkAdbAddress("10.238.15.91:30001"), true);
  assert.equal(isNetworkAdbAddress("localhost:5555"), true);
  // 本地序列号 / emulator / 空值不算网络地址
  assert.equal(isNetworkAdbAddress("emulator-5554"), false);
  assert.equal(isNetworkAdbAddress("9YS0219B28024240"), false);
  assert.equal(isNetworkAdbAddress(undefined), false);
  assert.equal(isNetworkAdbAddress(""), false);
});

test("ensureAdbConnected 对网络地址执行 adb connect", async () => {
  const calls: Array<{ file: string; args: string[] }> = [];
  await ensureAdbConnected("10.238.15.91:30001", {
    exec: async (file, args) => {
      calls.push({ file, args });
      return { stdout: "connected to 10.238.15.91:30001", stderr: "" };
    }
  });
  assert.equal(calls.length, 1);
  assert.deepEqual(calls[0], { file: "adb", args: ["connect", "10.238.15.91:30001"] });
});

test("ensureAdbConnected 对非网络地址跳过 connect", async () => {
  let called = false;
  await ensureAdbConnected("emulator-5554", {
    exec: async () => {
      called = true;
      return { stdout: "", stderr: "" };
    }
  });
  assert.equal(called, false);
});

test("ensureAdbConnected 在 adb 执行抛错时不抛出（不阻断执行）", async () => {
  await assert.doesNotReject(() =>
    ensureAdbConnected("10.238.15.91:30001", {
      exec: async () => {
        throw new Error("adb: command not found");
      }
    })
  );
});

test("ensureAdbConnected 在 connect 文案含 failed 时不抛出", async () => {
  await assert.doesNotReject(() =>
    ensureAdbConnected("10.238.15.91:30001", {
      exec: async () => ({ stdout: "", stderr: "failed to connect to '10.238.15.91:30001'" })
    })
  );
});
