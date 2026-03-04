import { agentFromAdbDevice } from "@midscene/android";
import type { ExecutionDump } from "@midscene/core";
import { parseYamlScript } from "@midscene/core/yaml";
import type { RunProgressPatch, RunResultPayload, RunStartPayload } from "../types.js";

export interface YamlRunnerHooks {
  onProgress: (progress: RunProgressPatch) => void;
  onSuccess: (result: RunResultPayload) => void;
  onFailed: (result: RunResultPayload) => void;
  onCancelled: () => void;
}

interface ActiveRunHandle {
  cancelRequested: boolean;
  cancel: () => Promise<void>;
}

function formatErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === "string") return error;
  try {
    return JSON.stringify(error);
  } catch {
    return "Unknown error";
  }
}

/**
 * 对上游模型/执行异常进行归一化，避免前端展示大段技术栈。
 * 说明：
 * - 日志仍会记录原始错误，便于排查；
 * - 返回文案用于 run.error_message，强调“可操作的下一步”。
 */
export function normalizeUserFacingErrorMessage(rawMessage: string): string {
  const normalizedRaw = rawMessage.trim();
  const lower = normalizedRaw.toLowerCase();

  if (
    lower.includes("free tier of the model has been exhausted") ||
    (lower.includes("403") && lower.includes("free tier"))
  ) {
    return "模型调用失败：当前模型免费额度已用尽（403）。请在模型平台关闭“仅免费额度”限制或充值后重试。";
  }

  if (
    lower.includes("model configuration is incomplete") ||
    lower.includes("midscene_model_name") && lower.includes("required")
  ) {
    return "模型配置不完整：请在 runner-service 进程环境中配置 MIDSCENE_MODEL_NAME（及对应 API_KEY/BASE_URL/FAMILY）后重试。";
  }

  // 去掉冗长堆栈，只保留业务错误主干信息。
  const stackStart = normalizedRaw.search(/\s+at\s+[A-Za-z0-9_$.<]/);
  const noStack = stackStart > 0 ? normalizedRaw.slice(0, stackStart).trim() : normalizedRaw;
  const errorLabel = "Error(s) occurred in running yaml script:";
  const labelIndex = noStack.indexOf(errorLabel);
  if (labelIndex >= 0) {
    return noStack.slice(labelIndex + errorLabel.length).trim() || "YAML 脚本执行失败。";
  }
  return noStack;
}

function extractTaskLabel(task: any): string | null {
  if (!task || typeof task !== "object") return null;
  return (
    task?.subType ||
    task?.param?.name ||
    task?.param?.prompt ||
    task?.thought ||
    task?.type ||
    null
  );
}

export function buildProgressFromDump(executionDump: ExecutionDump): RunProgressPatch {
  const tasks = Array.isArray(executionDump.tasks) ? executionDump.tasks : [];
  const total = tasks.length;
  const completed = tasks.filter((task) =>
    ["finished", "failed", "cancelled"].includes(task?.status)
  ).length;

  const runningTask = tasks.find((task) => task?.status === "running");
  const latestTask = runningTask || tasks[total - 1];

  return {
    total,
    completed,
    currentTask: latestTask ? extractTaskLabel(latestTask) : null,
    currentAction: latestTask ? extractTaskLabel(latestTask) : null,
    executionDump
  };
}

export function resolveTargetDeviceId(
  payloadDeviceId?: string | null,
  yamlDeviceId?: string | null
): string | undefined {
  const fromPayload = payloadDeviceId?.trim();
  if (fromPayload) return fromPayload;
  const fromYaml = yamlDeviceId?.trim();
  if (fromYaml) return fromYaml;
  return undefined;
}

/**
 * 基于 Midscene Agent 的 YAML 执行服务：
 * - startRun：异步执行 YAML，并持续回调结构化进度
 * - cancelRun：中断执行（destroy agent）
 */
export class YamlRunner {
  private readonly activeRuns = new Map<number, ActiveRunHandle>();

  startRun(payload: RunStartPayload, hooks: YamlRunnerHooks): void {
    if (this.activeRuns.has(payload.runId)) {
      throw new Error(`Run ${payload.runId} is already running`);
    }

    const handle: ActiveRunHandle = {
      cancelRequested: false,
      cancel: async () => {
        handle.cancelRequested = true;
        // agent 实例在执行协程内注入
        if (typeof (handle as any).destroyAgent === "function") {
          await (handle as any).destroyAgent();
        }
      }
    };

    this.activeRuns.set(payload.runId, handle);
    console.info(`[yaml-runner] 开始执行 runId=${payload.runId}`);

    (async () => {
      let agent: Awaited<ReturnType<typeof agentFromAdbDevice>> | null = null;
      try {
        const parsed = parseYamlScript(payload.yamlContent, `run-${payload.runId}.yaml`);
        const targetDeviceId = resolveTargetDeviceId(
          payload.deviceId,
          parsed.android?.deviceId
        );

        if (targetDeviceId) {
          console.info(
            `[yaml-runner] 使用指定设备 runId=${payload.runId}, deviceId=${targetDeviceId}`
          );
        } else {
          console.info(
            `[yaml-runner] 未指定deviceId，自动连接首台在线设备 runId=${payload.runId}`
          );
        }

        agent = await agentFromAdbDevice(targetDeviceId, {
          ...(parsed.android || {})
        });
        (handle as any).destroyAgent = async () => {
          if (agent) {
            await agent.destroy();
          }
        };

        agent.onDumpUpdate = (_dump: string, executionDump?: ExecutionDump) => {
          if (!executionDump) return;
          const patch = buildProgressFromDump(executionDump);
          hooks.onProgress(patch);
        };

        await agent.runYaml(payload.yamlContent);
        if (handle.cancelRequested) {
          console.info(`[yaml-runner] 执行已取消 runId=${payload.runId}`);
          hooks.onCancelled();
          return;
        }

        const reportPath = (agent as any).reportFile || null;
        console.info(`[yaml-runner] 执行成功 runId=${payload.runId}`);
        hooks.onSuccess({
          reportPath,
          summaryPath: null,
          errorMessage: null
        });
      } catch (error) {
        if (handle.cancelRequested) {
          console.info(`[yaml-runner] 取消后退出 runId=${payload.runId}`);
          hooks.onCancelled();
          return;
        }
        const reportPath = (agent as any)?.reportFile || null;
        const rawMessage = formatErrorMessage(error);
        const userMessage = normalizeUserFacingErrorMessage(rawMessage);
        console.error(
          `[yaml-runner] 执行失败 runId=${payload.runId}, userError=${userMessage}, rawError=${rawMessage}`
        );
        hooks.onFailed({
          reportPath,
          summaryPath: null,
          errorMessage: userMessage
        });
      } finally {
        this.activeRuns.delete(payload.runId);
        if (agent) {
          try {
            await agent.destroy();
          } catch (destroyError) {
            console.warn(
              `[yaml-runner] 销毁agent失败 runId=${payload.runId}, error=${formatErrorMessage(
                destroyError
              )}`
            );
          }
        }
      }
    })().catch((error) => {
      // 兜底，避免未捕获 Promise 异常导致进程崩溃。
      console.error(
        `[yaml-runner] 执行协程异常 runId=${payload.runId}, error=${formatErrorMessage(error)}`
      );
      this.activeRuns.delete(payload.runId);
    });
  }

  async cancelRun(runId: number): Promise<boolean> {
    const handle = this.activeRuns.get(runId);
    if (!handle) return false;
    await handle.cancel();
    return true;
  }
}
