import Fastify from "fastify";
import { pathToFileURL } from "node:url";
import { loadConfig } from "./config.js";
import { RunManager, RunStateError } from "./services/run-manager.js";
import { YamlRunner } from "./services/yaml-runner.js";
import type { RunStartPayload } from "./types.js";

const config = loadConfig();
const runManager = new RunManager();
const yamlRunner = new YamlRunner();

function asRunId(raw: string): number {
  const runId = Number(raw);
  if (!Number.isInteger(runId) || runId <= 0) {
    throw new RunStateError("INVALID_RUN_ID", `Invalid runId: ${raw}`);
  }
  return runId;
}

function mapErrorStatus(error: unknown): number {
  if (!(error instanceof RunStateError)) return 500;
  if (error.code === "RUN_NOT_FOUND" || error.code === "INVALID_RUN_ID") return 404;
  if (error.code === "RUN_ALREADY_ACTIVE") return 409;
  if (error.code === "RUN_TERMINAL") return 409;
  return 400;
}

function applyRunMutationSafely(
  app: ReturnType<typeof Fastify>,
  label: string,
  runId: number,
  mutate: () => void
): void {
  try {
    mutate();
  } catch (error) {
    if (error instanceof RunStateError && error.code === "RUN_TERMINAL") {
      app.log.warn(`[${label}] run已终态，跳过更新 runId=${runId}`);
      return;
    }
    app.log.error({ err: error }, `[${label}] run状态更新失败 runId=${runId}`);
  }
}

/**
 * Runner HTTP 服务入口：
 * 提供任务启动、进度查询、取消与结果查询接口。
 */
export function createServer() {
  const app = Fastify({
    logger: true
  });

  app.get("/health", async () => {
    app.log.info("健康检查请求已处理");
    return { status: "ok" };
  });

  app.post<{ Body: RunStartPayload }>("/runs/start", async (request, reply) => {
    try {
      const payload = request.body;
      if (!payload || !payload.runId || !payload.yamlContent?.trim()) {
        return reply.status(400).send({
          error: "runId 和 yamlContent 为必填项"
        });
      }

      runManager.createRun(payload);
      runManager.startRun(payload.runId);

      yamlRunner.startRun(payload, {
        onProgress: (progress) => {
          applyRunMutationSafely(app, "onProgress", payload.runId, () => {
            runManager.updateProgress(payload.runId, progress);
          });
        },
        onSuccess: (result) => {
          applyRunMutationSafely(app, "onSuccess", payload.runId, () => {
            runManager.markSuccess(payload.runId, result);
          });
        },
        onFailed: (result) => {
          applyRunMutationSafely(app, "onFailed", payload.runId, () => {
            runManager.markFailed(payload.runId, result);
          });
        },
        onCancelled: () => {
          applyRunMutationSafely(app, "onCancelled", payload.runId, () => {
            runManager.cancelRun(payload.runId);
          });
        }
      });

      app.log.info(`run启动成功 runId=${payload.runId}`);
      return {
        accepted: true,
        runId: payload.runId
      };
    } catch (error) {
      const statusCode = mapErrorStatus(error);
      app.log.error({ err: error }, "run启动失败");
      return reply.status(statusCode).send({
        error: error instanceof Error ? error.message : "Unknown error"
      });
    }
  });

  app.get<{ Params: { runId: string } }>("/runs/:runId/progress", async (request, reply) => {
    try {
      const runId = asRunId(request.params.runId);
      const run = runManager.getRun(runId);
      if (!run) {
        return reply.status(404).send({ error: `Run ${runId} not found` });
      }
      app.log.info(
        `[progress] runId=${runId}, status=${run.status}, task=${run.currentTask ?? "-"}, action=${run.currentAction ?? "-"}, completed=${run.completed}/${run.total}`
      );
      return {
        runId: run.runId,
        status: run.status,
        currentTask: run.currentTask,
        currentAction: run.currentAction,
        completed: run.completed,
        total: run.total,
        executionDump: run.executionDump,
        updatedAt: run.updatedAt
      };
    } catch (error) {
      const statusCode = mapErrorStatus(error);
      return reply.status(statusCode).send({
        error: error instanceof Error ? error.message : "Unknown error"
      });
    }
  });

  /**
   * SSE 进度流：
   * - 首次连接会先下发一次 snapshot
   * - 后续按 progress / done 事件实时推送
   */
  app.get<{ Params: { runId: string } }>("/runs/:runId/stream", async (request, reply) => {
    try {
      const runId = asRunId(request.params.runId);
      const run = runManager.getRun(runId);
      if (!run) {
        return reply.status(404).send({ error: `Run ${runId} not found` });
      }

      reply.raw.setHeader("Content-Type", "text/event-stream; charset=utf-8");
      reply.raw.setHeader("Cache-Control", "no-cache, no-transform");
      reply.raw.setHeader("Connection", "keep-alive");
      reply.raw.flushHeaders();

      const writeEvent = (name: string, payload: unknown) => {
        reply.raw.write(`event: ${name}\n`);
        reply.raw.write(`data: ${JSON.stringify(payload)}\n\n`);
      };

      app.log.info(`[stream] SSE连接建立 runId=${runId}`);

      // 先给一帧当前快照，避免前端空白等待。
      writeEvent("snapshot", {
        runId: run.runId,
        status: run.status,
        currentTask: run.currentTask,
        currentAction: run.currentAction,
        completed: run.completed,
        total: run.total,
        executionDump: run.executionDump,
        updatedAt: run.updatedAt
      });

      const heartbeat = setInterval(() => {
        reply.raw.write(": heartbeat\n\n");
      }, 15_000);

      const unsubscribe = runManager.subscribe(runId, (event) => {
        const payload = {
          runId: event.run.runId,
          status: event.run.status,
          currentTask: event.run.currentTask,
          currentAction: event.run.currentAction,
          completed: event.run.completed,
          total: event.run.total,
          executionDump: event.run.executionDump,
          updatedAt: event.run.updatedAt,
          reportPath: event.run.reportPath,
          errorMessage: event.run.errorMessage
        };
        writeEvent(event.type, payload);
      });

      request.raw.on("close", () => {
        clearInterval(heartbeat);
        unsubscribe();
        app.log.info(`[stream] SSE连接关闭 runId=${runId}`);
      });

      return reply;
    } catch (error) {
      const statusCode = mapErrorStatus(error);
      return reply.status(statusCode).send({
        error: error instanceof Error ? error.message : "Unknown error"
      });
    }
  });

  app.post<{ Params: { runId: string } }>("/runs/:runId/cancel", async (request, reply) => {
    try {
      const runId = asRunId(request.params.runId);
      const run = runManager.getRun(runId);
      if (!run) {
        return reply.status(404).send({ error: `Run ${runId} not found` });
      }

      // 已终态时直接幂等返回
      if (["success", "failed", "cancelled"].includes(run.status)) {
        return {
          success: true,
          runId,
          status: run.status,
          message: "Run already terminal"
        };
      }

      const cancelled = await yamlRunner.cancelRun(runId);
      if (!cancelled) {
        // 执行器已无活跃句柄，直接落 cancel 态，避免悬挂。
        runManager.cancelRun(runId);
        app.log.warn(`[cancel] runId=${runId} 无活跃执行句柄，直接标记cancelled`);
      } else {
        // 先更新状态给调用方快速反馈，后续 onCancelled 会幂等处理。
        runManager.cancelRun(runId);
        app.log.info(`[cancel] runId=${runId} 已请求执行器取消`);
      }

      return {
        success: true,
        runId,
        status: "cancelled"
      };
    } catch (error) {
      const statusCode = mapErrorStatus(error);
      app.log.error({ err: error }, "run取消失败");
      return reply.status(statusCode).send({
        error: error instanceof Error ? error.message : "Unknown error"
      });
    }
  });

  app.get<{ Params: { runId: string } }>("/runs/:runId/result", async (request, reply) => {
    try {
      const runId = asRunId(request.params.runId);
      const run = runManager.getRun(runId);
      if (!run) {
        return reply.status(404).send({ error: `Run ${runId} not found` });
      }
      app.log.info(
        `[result] runId=${runId}, status=${run.status}, report=${run.reportPath ?? "-"}, error=${run.errorMessage ?? "-"}`
      );
      return {
        runId: run.runId,
        status: run.status,
        reportPath: run.reportPath,
        summaryPath: run.summaryPath,
        errorMessage: run.errorMessage,
        startedAt: run.startedAt,
        endedAt: run.endedAt,
        updatedAt: run.updatedAt
      };
    } catch (error) {
      const statusCode = mapErrorStatus(error);
      return reply.status(statusCode).send({
        error: error instanceof Error ? error.message : "Unknown error"
      });
    }
  });

  return app;
}

async function bootstrap() {
  const app = createServer();
  try {
    await app.listen({
      host: config.host,
      port: config.port
    });
    app.log.info(`Runner service listening at http://${config.host}:${config.port}`);
  } catch (error) {
    app.log.error(error, "Failed to start runner service");
    process.exit(1);
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  bootstrap();
}
