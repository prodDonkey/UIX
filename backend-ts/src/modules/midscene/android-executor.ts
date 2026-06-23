import { agentFromAdbDevice } from "@midscene/android";
import { existsSync, readdirSync } from "node:fs";
import { join } from "node:path";
import YAML from "yaml";

import type { SceneExecutionResult } from "./types.js";

const MIDSCENE_REPORT_DIR = join(process.cwd(), "midscene_run", "report");

// 列出报告目录下的 html 文件名集合，目录不存在时返回空集
function listReportFiles(): Set<string> {
  if (!existsSync(MIDSCENE_REPORT_DIR)) {
    return new Set();
  }
  return new Set(readdirSync(MIDSCENE_REPORT_DIR).filter((name) => name.endsWith(".html")));
}

export class AndroidExecutionError extends Error {}

type AndroidYamlAgent = {
  runYaml: (yamlScriptContent: string) => Promise<{ result: Record<string, unknown> }>;
  destroy: () => Promise<void>;
};

type AndroidExecutorDeps = {
  createAgent?: (deviceId?: string) => Promise<AndroidYamlAgent>;
};

export async function executeSceneAndroidYaml(
  params: {
    yamlContent: string;
    defaultDeviceId?: string;
  },
  deps: AndroidExecutorDeps = {}
): Promise<SceneExecutionResult> {
  ensureMidsceneModelEnv();
  const parsed = parseAndroidYaml(params.yamlContent);
  const tasks = parsed.tasks;
  const androidConfig = parsed.android;
  const yamlDeviceId = typeof androidConfig.deviceId === "string" ? androidConfig.deviceId.trim() : "";
  const deviceId = yamlDeviceId || params.defaultDeviceId || undefined;
  const createAgent = deps.createAgent ?? ((nextDeviceId?: string) => agentFromAdbDevice(nextDeviceId));

  let agent: AndroidYamlAgent | null = null;
  const reportsBefore = listReportFiles();
  try {
    agent = await createAgent(deviceId);
    const execution = await agent.runYaml(params.yamlContent);
    const outputs = isRecord(execution.result) ? execution.result : {};
    // 采集本次执行新增的 Midscene HTML 报告，供上层（skill）定位
    const reportsAfter = listReportFiles();
    const newReports = [...reportsAfter].filter((name) => !reportsBefore.has(name));
    return {
      success: true,
      message: "场景执行完成",
      outputs: { ...outputs, report_files: newReports },
      task_results: tasks.map((task) => ({
        task_name: String(task.name ?? ""),
        ok: true
      })),
      result: outputs
    };
  } catch (error) {
    throw new AndroidExecutionError(
      `Midscene Android 执行失败：${error instanceof Error ? error.message : String(error)}`
    );
  } finally {
    await agent?.destroy();
  }
}

function ensureMidsceneModelEnv() {
  patchEnv("MIDSCENE_MODEL_NAME", process.env.MIDSCENE_MODEL_NAME, process.env.LLM_MODEL_NAME);
  patchEnv("MIDSCENE_MODEL_BASE_URL", process.env.MIDSCENE_MODEL_BASE_URL, process.env.LLM_BASE_URL);
  patchEnv("MIDSCENE_MODEL_API_KEY", process.env.MIDSCENE_MODEL_API_KEY, process.env.LLM_API_KEY);
  patchEnv("MIDSCENE_MODEL_FAMILY", process.env.MIDSCENE_MODEL_FAMILY, process.env.LLM_MODEL_FAMILY);

  const missingKeys = [
    "MIDSCENE_MODEL_NAME",
    "MIDSCENE_MODEL_BASE_URL",
    "MIDSCENE_MODEL_API_KEY",
    "MIDSCENE_MODEL_FAMILY"
  ].filter((key) => !String(process.env[key] ?? "").trim());

  if (missingKeys.length > 0) {
    throw new AndroidExecutionError(
      `Midscene 模型配置不完整，缺少：${missingKeys.join(", ")}。` +
        " 请在 .env 中补齐 MIDSCENE_MODEL_*，或提供兼容的 LLM_* 映射。"
    );
  }
}

function patchEnv(key: string, primaryValue: string | undefined, fallbackValue: string | undefined) {
  if (String(primaryValue ?? "").trim()) {
    return;
  }
  if (String(fallbackValue ?? "").trim()) {
    process.env[key] = String(fallbackValue).trim();
  }
}

function parseAndroidYaml(content: string): { android: Record<string, unknown>; tasks: Record<string, unknown>[] } {
  let parsed: unknown;
  try {
    parsed = YAML.parse(content) ?? {};
  } catch (error) {
    throw new AndroidExecutionError(
      `Android 脚本 YAML 解析失败：${error instanceof Error ? error.message : String(error)}`
    );
  }

  if (!isRecord(parsed)) {
    throw new AndroidExecutionError("Android 脚本内容必须是对象");
  }
  if (!isRecord(parsed.android)) {
    throw new AndroidExecutionError("当前场景不是 Android 脚本，缺少 android 配置");
  }
  if (!Array.isArray(parsed.tasks) || parsed.tasks.length === 0) {
    throw new AndroidExecutionError("Android 脚本缺少可执行 tasks");
  }

  const tasks = parsed.tasks.filter(isRecord);
  if (tasks.length !== parsed.tasks.length) {
    throw new AndroidExecutionError("Android 脚本 tasks 存在非法任务结构");
  }

  return {
    android: parsed.android,
    tasks
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
