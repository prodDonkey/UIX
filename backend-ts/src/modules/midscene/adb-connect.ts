import { execFile } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

// 网络 adb 地址形如 host:port（如 10.238.15.91:30001）。
// 本地序列号 / emulator-5554 等不匹配，跳过 connect。
const NETWORK_ADDR_PATTERN = /^[^:\s]+:\d+$/;

// adb connect 的超时（毫秒）。网络设备偶尔握手较慢，给 15s。
const ADB_CONNECT_TIMEOUT_MS = 15000;

type ExecLike = (
  file: string,
  args: string[],
  options: { encoding: "utf8"; timeout: number }
) => Promise<{ stdout: string; stderr: string }>;

type EnsureAdbConnectedDeps = {
  exec?: ExecLike;
};

/**
 * 判断 deviceId 是否为网络 adb 地址（需要先 adb connect 才能被 Midscene 选中）。
 */
export function isNetworkAdbAddress(deviceId: string | undefined): boolean {
  return typeof deviceId === "string" && NETWORK_ADDR_PATTERN.test(deviceId.trim());
}

/**
 * 对网络 adb 地址执行 `adb connect <deviceId>`，确保设备进入本地 adb 设备列表，
 * 之后 Midscene 的 agentFromAdbDevice 才能选中它（Midscene 本身不会自动 connect）。
 *
 * 设计要点：
 * - 仅对 host:port 形态的地址执行；本地序列号直接跳过。
 * - connect 失败不抛错：设备可能已被其它途径连上，交给 Midscene 再尝试，
 *   仅打告警日志（含 deviceId 与 stderr）便于排障。
 */
export async function ensureAdbConnected(
  deviceId: string | undefined,
  deps: EnsureAdbConnectedDeps = {}
): Promise<void> {
  if (!isNetworkAdbAddress(deviceId)) {
    return;
  }
  const target = (deviceId as string).trim();
  const exec = deps.exec ?? (execFileAsync as unknown as ExecLike);

  try {
    const { stdout, stderr } = await exec("adb", ["connect", target], {
      encoding: "utf8",
      timeout: ADB_CONNECT_TIMEOUT_MS
    });
    const output = `${stdout ?? ""}${stderr ?? ""}`.trim();
    // adb connect 即使失败也常以退出码 0 返回，文案里带 "failed"/"cannot"/"unable"
    if (/fail|cannot|unable|refused|error/i.test(output)) {
      console.warn(`[adb-connect] 连接设备 ${target} 可能未成功：${output}`);
    } else {
      console.log(`[adb-connect] 已连接设备 ${target}：${output}`);
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    // 不阻断执行：交给 Midscene 再尝试，最终不可用时由其报错
    console.warn(`[adb-connect] adb connect ${target} 执行失败（不阻断执行）：${message}`);
  }
}
