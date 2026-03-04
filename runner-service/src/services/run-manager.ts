import type {
  RunProgressPatch,
  RunResultPayload,
  RunSnapshot,
  RunStartPayload,
  RunStatus
} from "../types.js";

/**
 * Runner 内存态管理器：
 * - 负责 run 生命周期（queued/running/terminal）
 * - 负责进度快照更新（currentTask/currentAction/completed/total）
 * - 不做持久化，持久化由 ui_demo backend 负责
 */
type RunRecord = Omit<
  RunSnapshot,
  "createdAt" | "startedAt" | "endedAt" | "updatedAt"
> & {
  createdAt: Date;
  startedAt: Date | null;
  endedAt: Date | null;
  updatedAt: Date;
};

const terminalStatuses: ReadonlySet<RunStatus> = new Set([
  "success",
  "failed",
  "cancelled"
]);

export class RunStateError extends Error {
  code: string;

  constructor(code: string, message: string) {
    super(message);
    this.code = code;
  }
}

export function isTerminalStatus(status: RunStatus): boolean {
  return terminalStatuses.has(status);
}

export class RunManager {
  private readonly runs = new Map<number, RunRecord>();

  createRun(payload: RunStartPayload): RunSnapshot {
    const existing = this.runs.get(payload.runId);
    if (existing && !isTerminalStatus(existing.status)) {
      console.warn(
        `[run-manager] run已存在且仍在执行中，拒绝重复创建 runId=${payload.runId}, status=${existing.status}`
      );
      throw new RunStateError(
        "RUN_ALREADY_ACTIVE",
        `Run ${payload.runId} is already active (${existing.status})`
      );
    }

    const now = new Date();
    const next: RunRecord = {
      runId: payload.runId,
      status: "queued",
      yamlContent: payload.yamlContent,
      deviceId: payload.deviceId ?? null,
      currentTask: null,
      currentAction: null,
      completed: 0,
      total: 0,
      executionDump: null,
      reportPath: null,
      summaryPath: null,
      errorMessage: null,
      createdAt: now,
      startedAt: null,
      endedAt: null,
      updatedAt: now
    };
    this.runs.set(payload.runId, next);
    console.info(`[run-manager] 创建run成功 runId=${payload.runId}, status=queued`);
    return this.toSnapshot(next);
  }

  startRun(runId: number): RunSnapshot {
    const run = this.getMutableOrThrow(runId);
    if (run.status === "running") {
      console.info(`[run-manager] run已处于running，幂等返回 runId=${runId}`);
      return this.toSnapshot(run);
    }
    if (isTerminalStatus(run.status)) {
      console.warn(
        `[run-manager] run已终态，禁止start runId=${runId}, status=${run.status}`
      );
      throw new RunStateError(
        "RUN_TERMINAL",
        `Run ${runId} is already terminal (${run.status})`
      );
    }

    const now = new Date();
    run.status = "running";
    run.startedAt = run.startedAt || now;
    run.updatedAt = now;
    console.info(`[run-manager] run进入running runId=${runId}`);
    return this.toSnapshot(run);
  }

  updateProgress(runId: number, patch: RunProgressPatch): RunSnapshot {
    const run = this.getMutableOrThrow(runId);
    if (isTerminalStatus(run.status)) {
      // 终态后忽略进度更新，避免覆盖最终结果
      console.info(
        `[run-manager] run已终态，忽略progress更新 runId=${runId}, status=${run.status}`
      );
      return this.toSnapshot(run);
    }

    const now = new Date();
    if (run.status === "queued") {
      run.status = "running";
      run.startedAt = run.startedAt || now;
    }

    if (patch.currentTask !== undefined) run.currentTask = patch.currentTask;
    if (patch.currentAction !== undefined) {
      run.currentAction = patch.currentAction;
    }
    if (patch.total !== undefined) run.total = Math.max(0, patch.total);
    if (patch.completed !== undefined) {
      run.completed = Math.max(0, patch.completed);
    }
    if (patch.executionDump !== undefined) {
      run.executionDump = patch.executionDump;
    }

    // Keep progress consistent even if upstream reports odd values.
    if (run.total > 0 && run.completed > run.total) {
      run.completed = run.total;
    }
    run.updatedAt = now;
    console.info(
      `[run-manager] 更新progress runId=${runId}, completed=${run.completed}, total=${run.total}, task=${run.currentTask ?? "-"}, action=${run.currentAction ?? "-"}`
    );
    return this.toSnapshot(run);
  }

  markSuccess(runId: number, payload: RunResultPayload = {}): RunSnapshot {
    const run = this.getMutableOrThrow(runId);
    if (run.status === "success") {
      console.info(`[run-manager] run已success，幂等返回 runId=${runId}`);
      return this.toSnapshot(run);
    }
    if (isTerminalStatus(run.status)) {
      console.warn(
        `[run-manager] run已终态，禁止markSuccess runId=${runId}, status=${run.status}`
      );
      throw new RunStateError(
        "RUN_TERMINAL",
        `Run ${runId} is already terminal (${run.status})`
      );
    }

    const now = new Date();
    run.status = "success";
    run.reportPath = payload.reportPath ?? run.reportPath;
    run.summaryPath = payload.summaryPath ?? run.summaryPath;
    run.errorMessage = null;
    run.endedAt = now;
    run.updatedAt = now;
    console.info(`[run-manager] run执行成功 runId=${runId}`);
    return this.toSnapshot(run);
  }

  markFailed(runId: number, payload: RunResultPayload = {}): RunSnapshot {
    const run = this.getMutableOrThrow(runId);
    if (run.status === "failed") {
      console.info(`[run-manager] run已failed，幂等返回 runId=${runId}`);
      return this.toSnapshot(run);
    }
    if (isTerminalStatus(run.status)) {
      console.warn(
        `[run-manager] run已终态，禁止markFailed runId=${runId}, status=${run.status}`
      );
      throw new RunStateError(
        "RUN_TERMINAL",
        `Run ${runId} is already terminal (${run.status})`
      );
    }

    const now = new Date();
    run.status = "failed";
    run.reportPath = payload.reportPath ?? run.reportPath;
    run.summaryPath = payload.summaryPath ?? run.summaryPath;
    run.errorMessage = payload.errorMessage ?? run.errorMessage;
    run.endedAt = now;
    run.updatedAt = now;
    console.error(
      `[run-manager] run执行失败 runId=${runId}, error=${run.errorMessage ?? "-"}`
    );
    return this.toSnapshot(run);
  }

  cancelRun(runId: number): RunSnapshot {
    const run = this.getMutableOrThrow(runId);
    if (run.status === "cancelled") {
      console.info(`[run-manager] run已cancelled，幂等返回 runId=${runId}`);
      return this.toSnapshot(run);
    }
    if (isTerminalStatus(run.status)) {
      console.warn(
        `[run-manager] run已终态，禁止cancel runId=${runId}, status=${run.status}`
      );
      throw new RunStateError(
        "RUN_TERMINAL",
        `Run ${runId} is already terminal (${run.status})`
      );
    }

    const now = new Date();
    run.status = "cancelled";
    run.endedAt = now;
    run.updatedAt = now;
    console.info(`[run-manager] run已取消 runId=${runId}`);
    return this.toSnapshot(run);
  }

  getRun(runId: number): RunSnapshot | null {
    const run = this.runs.get(runId);
    if (!run) return null;
    return this.toSnapshot(run);
  }

  listRuns(): RunSnapshot[] {
    return [...this.runs.values()]
      .sort((a, b) => b.runId - a.runId)
      .map((run) => this.toSnapshot(run));
  }

  private getMutableOrThrow(runId: number): RunRecord {
    const run = this.runs.get(runId);
    if (!run) {
      console.warn(`[run-manager] run不存在 runId=${runId}`);
      throw new RunStateError("RUN_NOT_FOUND", `Run ${runId} not found`);
    }
    return run;
  }

  private toSnapshot(run: RunRecord): RunSnapshot {
    return {
      ...run,
      createdAt: run.createdAt.toISOString(),
      startedAt: run.startedAt?.toISOString() ?? null,
      endedAt: run.endedAt?.toISOString() ?? null,
      updatedAt: run.updatedAt.toISOString()
    };
  }
}
