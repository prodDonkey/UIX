import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { config as loadDotenv } from "dotenv";

export interface RunnerConfig {
  host: string;
  port: number;
}

const defaultPort = 8100;
let envLoaded = false;

function ensureEnvLoaded(): void {
  if (envLoaded) return;

  // 以 runner-service/.env 为主，backend/.env 兜底补齐未提供项。
  const currentDir = dirname(fileURLToPath(import.meta.url));
  const runnerEnvPath = resolve(currentDir, "../.env");
  const backendEnvPath = resolve(currentDir, "../../backend/.env");

  if (existsSync(runnerEnvPath)) {
    loadDotenv({ path: runnerEnvPath, override: false });
    console.info(`[runner-config] 已加载环境变量文件: ${runnerEnvPath}`);
  }

  if (existsSync(backendEnvPath)) {
    loadDotenv({ path: backendEnvPath, override: false });
    console.info(`[runner-config] 已加载环境变量兜底文件: ${backendEnvPath}`);
  }

  // 报告产物默认写入 backend/midscene_run，避免预览接口触发“Report path not allowed”。
  if (!process.env.MIDSCENE_RUN_DIR) {
    process.env.MIDSCENE_RUN_DIR = resolve(currentDir, "../../backend/midscene_run");
    console.info(
      `[runner-config] 未配置MIDSCENE_RUN_DIR，已使用默认目录: ${process.env.MIDSCENE_RUN_DIR}`
    );
  }

  envLoaded = true;
}

function parsePort(rawPort: string | undefined): number {
  if (!rawPort) return defaultPort;
  const parsed = Number(rawPort);
  if (!Number.isInteger(parsed) || parsed <= 0 || parsed > 65535) {
    return defaultPort;
  }
  return parsed;
}

export function loadConfig(env: NodeJS.ProcessEnv = process.env): RunnerConfig {
  ensureEnvLoaded();
  return {
    host: env.RUNNER_HOST || "127.0.0.1",
    port: parsePort(env.RUNNER_PORT)
  };
}
