export type RunStatus =
  | "queued"
  | "running"
  | "success"
  | "failed"
  | "cancelled";

export interface RunStartPayload {
  runId: number;
  yamlContent: string;
  deviceId?: string | null;
}

export interface RunProgressPatch {
  currentTask?: string | null;
  currentAction?: string | null;
  completed?: number;
  total?: number;
  executionDump?: unknown;
}

export interface RunResultPayload {
  reportPath?: string | null;
  summaryPath?: string | null;
  errorMessage?: string | null;
}

export interface RunSnapshot {
  runId: number;
  status: RunStatus;
  yamlContent: string;
  deviceId: string | null;
  currentTask: string | null;
  currentAction: string | null;
  completed: number;
  total: number;
  executionDump: unknown | null;
  reportPath: string | null;
  summaryPath: string | null;
  errorMessage: string | null;
  createdAt: string;
  startedAt: string | null;
  endedAt: string | null;
  updatedAt: string;
}

export type RunStreamEventType = "snapshot" | "progress" | "done";

export interface RunStreamEvent {
  type: RunStreamEventType;
  run: RunSnapshot;
}
