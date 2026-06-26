import YAML from "yaml";

export const SCENE_VARIABLE_META_KEY = "sceneVariables";
const VARIABLE_PATTERN = /\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g;
const FULL_VARIABLE_PATTERN = /^\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}$/;

export class SceneCompileError extends Error {}

export type VariableRow = Record<string, string>;
export type TaskVariableMeta = {
  inputs: VariableRow[];
  outputs: VariableRow[];
};

export type ParsedScriptTask = {
  task_index: number;
  task_name: string;
  task: Record<string, unknown>;
  flow: unknown[];
  continue_on_error: boolean;
};

export function parseScriptTasks(content: string): ParsedScriptTask[] {
  const parsed = parseYamlObject(content, "脚本 YAML 解析失败");
  const tasks = parsed.tasks;
  if (tasks == null) {
    return [];
  }
  if (!Array.isArray(tasks)) {
    throw new SceneCompileError("脚本 tasks 必须是数组");
  }

  const interfaceConfig = parsed.interface;
  return tasks.map((task, index) => {
    if (!isRecord(task)) {
      throw new SceneCompileError(`第 ${index + 1} 个 task 结构非法`);
    }
    const name = String(task.name ?? "").trim();
    if (!name) {
      throw new SceneCompileError(`第 ${index + 1} 个 task 缺少 name`);
    }
    if (!Array.isArray(task.flow)) {
      throw new SceneCompileError(`task ${name} 缺少合法 flow`);
    }

    const taskSnapshot: Record<string, unknown> = { ...task };
    if (interfaceConfig !== undefined && taskSnapshot.interface === undefined) {
      taskSnapshot.interface = interfaceConfig;
    }

    return {
      task_index: index,
      task_name: name,
      task: taskSnapshot,
      flow: task.flow,
      continue_on_error: Boolean(task.continueOnError ?? false)
    };
  });
}

export function dumpTaskSnapshot(task: Record<string, unknown>): string {
  return YAML.stringify(task).trim();
}

export function loadTaskSnapshot(content: string): Record<string, unknown> {
  const parsed = parseYamlObject(content, "任务快照解析失败");
  return parsed;
}

export function extractScriptEnv(content: string): Record<string, unknown> {
  const parsed = parseYamlObject(content, "脚本 YAML 解析失败");
  const env: Record<string, unknown> = {};
  for (const key of ["android", "ios", "web", "computer", "agent", "config", "target"]) {
    if (parsed[key] !== undefined) {
      env[key] = parsed[key];
    }
  }
  return env;
}

export function compileSceneScript(env: Record<string, unknown>, taskSnapshots: string[]): string {
  const tasks: Record<string, unknown>[] = [];
  const availableVariables = new Set<string>();
  taskSnapshots.forEach((item, index) => {
    const task = loadTaskSnapshot(item);
    const meta = extractTaskVariableMeta(task);
    validateTaskVariableMeta(meta, availableVariables, index);
    tasks.push(task);
    for (const output of meta.outputs) {
      availableVariables.add(output.name);
    }
  });
  return YAML.stringify({ ...env, tasks });
}

export function taskSnapshotKey(taskSnapshot: string): string {
  return JSON.stringify(loadTaskSnapshot(taskSnapshot));
}

export function findScriptTask(content: string, taskIndex: number): ParsedScriptTask | null {
  return parseScriptTasks(content).find((item) => item.task_index === taskIndex) ?? null;
}

export function sceneTaskSyncStatus(params: {
  scriptContent: string;
  taskIndex: number;
  taskNameSnapshot: string;
  taskContentSnapshot: string;
}): [string, string] {
  const matchedTask = findScriptTask(params.scriptContent, params.taskIndex);
  if (!matchedTask) {
    return ["missing", "脚本中已不存在该任务"];
  }

  const currentMeta = taskSnapshotVariableMeta(params.taskContentSnapshot);
  const currentSnapshot = dumpTaskSnapshot(
    mergeTaskVariableMeta(matchedTask.task, {
      inputBindings: currentMeta.inputs,
      outputVariables: currentMeta.outputs
    })
  );
  if (
    matchedTask.task_name !== params.taskNameSnapshot ||
    taskSnapshotKey(currentSnapshot) !== taskSnapshotKey(params.taskContentSnapshot)
  ) {
    return ["stale", "脚本任务已更新，可同步快照"];
  }
  return ["current", ""];
}

export function applyTaskVariableMeta(
  task: Record<string, unknown>,
  params: {
    inputBindings?: VariableRow[] | null;
    outputVariables?: VariableRow[] | null;
  } = {}
): Record<string, unknown> {
  const nextTask = { ...task };
  const normalizedInputs = normalizeVariableRows(params.inputBindings ?? [], "输入绑定");
  const normalizedOutputs = normalizeVariableRows(params.outputVariables ?? [], "输出变量");
  if (normalizedInputs.length === 0 && normalizedOutputs.length === 0) {
    delete nextTask[SCENE_VARIABLE_META_KEY];
    return nextTask;
  }
  nextTask[SCENE_VARIABLE_META_KEY] = {
    inputs: normalizedInputs,
    outputs: normalizedOutputs
  };
  return nextTask;
}

export function mergeTaskVariableMeta(
  task: Record<string, unknown>,
  params: {
    inputBindings?: VariableRow[] | null;
    outputVariables?: VariableRow[] | null;
  } = {}
): Record<string, unknown> {
  const baseMeta = extractTaskVariableMeta(task);
  const normalizedInputs = normalizeVariableRows(params.inputBindings ?? [], "输入绑定");
  const normalizedOutputs = normalizeVariableRows(params.outputVariables ?? [], "输出变量");
  const mergedInputs = mergeVariableRows(baseMeta.inputs, normalizedInputs, "target_path");
  const mergedOutputs = mergeVariableRows(baseMeta.outputs, normalizedOutputs, "name");
  return applyTaskVariableMeta(task, {
    inputBindings: mergedInputs,
    outputVariables: mergedOutputs
  });
}

export function extractTaskVariableMeta(task: Record<string, unknown>): TaskVariableMeta {
  const rawMeta = task[SCENE_VARIABLE_META_KEY];
  if (!isRecord(rawMeta)) {
    return { inputs: [], outputs: [] };
  }
  return {
    inputs: normalizeVariableRows(Array.isArray(rawMeta.inputs) ? rawMeta.inputs : [], "输入绑定"),
    outputs: normalizeVariableRows(Array.isArray(rawMeta.outputs) ? rawMeta.outputs : [], "输出变量")
  };
}

export function taskSnapshotVariableMeta(taskSnapshot: string): TaskVariableMeta {
  return extractTaskVariableMeta(loadTaskSnapshot(taskSnapshot));
}

function validateTaskVariableMeta(meta: TaskVariableMeta, availableVariables: Set<string>, index: number) {
  const seenOutputs = new Set<string>();
  for (const output of meta.outputs) {
    const name = String(output.name ?? "").trim();
    if (!name) {
      throw new SceneCompileError(`第 ${index + 1} 个任务的输出变量缺少 name`);
    }
    if (!FULL_VARIABLE_PATTERN.test(`\${${name}}`)) {
      throw new SceneCompileError(`第 ${index + 1} 个任务的输出变量名非法：${name}`);
    }
    if (seenOutputs.has(name)) {
      throw new SceneCompileError(`第 ${index + 1} 个任务存在重复输出变量：${name}`);
    }
    seenOutputs.add(name);
  }

  for (const binding of meta.inputs) {
    const expression = String(binding.expression ?? "").trim();
    const targetPath = String(binding.target_path ?? "").trim();
    if (!targetPath) {
      throw new SceneCompileError(`第 ${index + 1} 个任务的输入绑定缺少 target_path`);
    }
    if (!expression) {
      throw new SceneCompileError(`第 ${index + 1} 个任务的输入绑定缺少 expression`);
    }

    const matches = expression.matchAll(VARIABLE_PATTERN);
    for (const match of matches) {
      const variableName = match[1];
      if (!availableVariables.has(variableName)) {
        throw new SceneCompileError(
          `第 ${index + 1} 个任务引用了未定义变量：${variableName}。只能引用前序任务输出变量`
        );
      }
    }
  }
}

function mergeVariableRows(baseRows: VariableRow[], overrideRows: VariableRow[], identityKey: string): VariableRow[] {
  const merged: VariableRow[] = [];
  const overrideIndex = new Map<string, VariableRow>();
  for (const row of overrideRows) {
    const rowKey = String(row[identityKey] ?? "").trim();
    if (rowKey) {
      overrideIndex.set(rowKey, row);
    }
  }

  const consumedKeys = new Set<string>();
  for (const row of baseRows) {
    const rowKey = String(row[identityKey] ?? "").trim();
    if (rowKey && overrideIndex.has(rowKey)) {
      merged.push(overrideIndex.get(rowKey)!);
      consumedKeys.add(rowKey);
      continue;
    }
    merged.push(row);
  }

  for (const row of overrideRows) {
    const rowKey = String(row[identityKey] ?? "").trim();
    if (rowKey && consumedKeys.has(rowKey)) {
      continue;
    }
    merged.push(row);
  }
  return merged;
}

function normalizeVariableRows(rows: unknown[], kind: string): VariableRow[] {
  const normalized: VariableRow[] = [];
  for (const row of rows) {
    if (!isRecord(row)) {
      throw new SceneCompileError(`${kind} 配置项必须是对象`);
    }
    const cleaned = Object.fromEntries(
      Object.entries(row)
        .filter(([, value]) => value != null && String(value).trim())
        .map(([key, value]) => [key, String(value).trim()])
    );
    if (Object.keys(cleaned).length > 0) {
      normalized.push(cleaned);
    }
  }
  return normalized;
}

function parseYamlObject(content: string, prefix: string): Record<string, unknown> {
  let parsed: unknown;
  try {
    parsed = YAML.parse(content) ?? {};
  } catch (error) {
    throw new SceneCompileError(`${prefix}：${error instanceof Error ? error.message : String(error)}`);
  }
  if (!isRecord(parsed)) {
    throw new SceneCompileError("脚本内容必须是对象结构");
  }
  return parsed;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}
