export type SceneExecutionResult = {
  success: boolean;
  message: string;
  outputs: Record<string, unknown>;
  task_results: Array<Record<string, unknown>>;
  result?: Record<string, unknown>;
};
