import { execFile } from "node:child_process";
import { promisify } from "node:util";

import { env } from "../config.js";
import { loadTaskSnapshot, taskSnapshotVariableMeta } from "./scene-compiler.js";

const execFileAsync = promisify(execFile);
const VARIABLE_PATTERN = /\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g;
const FULL_VARIABLE_PATTERN = /^\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}$/;
const PATH_SEGMENT_PATTERN = /([^\.\[\]]+)|\[(\d+)\]/g;
const MISSING = Symbol("missing");

export class HttpExecutionError extends Error {}

type VariableDefinition = Record<string, unknown>;
type InterfaceConfig = {
  method: string;
  url: string;
  contentType: string;
  headers: Record<string, string>;
  query: Record<string, unknown>;
  params?: unknown;
  body?: unknown;
  json?: unknown;
};

export async function executeSceneHttpTasks(params: {
  taskSnapshots: string[];
  timeoutSec: number;
}) {
  const outputs: Record<string, unknown> = {};
  const taskResults: Array<Record<string, unknown>> = [];

  for (const [index, snapshot] of params.taskSnapshots.entries()) {
    const rawTask = loadTaskSnapshot(snapshot);
    const task = structuredClone(rawTask);
    const taskName = String(task.name ?? `task-${index + 1}`);
    const variableMeta = taskSnapshotVariableMeta(snapshot);
    const continueOnError = Boolean(task.continueOnError ?? false);
    const runtimeDefaults = buildRuntimeDefaults();

    try {
      const runtimeVariables = { ...runtimeDefaults, ...outputs };
      applyInputBindings(task, variableMeta.inputs, runtimeVariables);
      let interfaceConfig = extractInterfaceConfig(task, index);
      interfaceConfig = applyKnownVariables(interfaceConfig, runtimeVariables) as InterfaceConfig;
      ensureInterfaceVariablesResolved(interfaceConfig);
      const startAt = Date.now();
      const response = await sendInterfaceRequest(interfaceConfig, params.timeoutSec);
      const durationMs = Date.now() - startAt;
      const responsePayload = await buildResponsePayload(response, interfaceConfig.url);
      raiseForBusinessError(responsePayload);
      const producedOutputs = extractOutputVariables(variableMeta.outputs, responsePayload);
      Object.assign(outputs, producedOutputs);
      taskResults.push({
        task_name: taskName,
        ok: true,
        method: interfaceConfig.method,
        url: interfaceConfig.url,
        status_code: responsePayload.status_code,
        duration_ms: durationMs,
        outputs: producedOutputs,
        response: responsePayload.body
      });
    } catch (error) {
      taskResults.push({
        task_name: taskName,
        ok: false,
        method: safeReadInterfaceField(task, "method"),
        url: safeReadInterfaceField(task, "url"),
        status_code: null,
        duration_ms: null,
        outputs: {},
        error: error instanceof Error ? error.message : String(error)
      });
      if (continueOnError) {
        continue;
      }
      return {
        success: false,
        message: `场景执行失败：${taskName}`,
        outputs,
        task_results: taskResults
      };
    }
  }

  return {
    success: true,
    message: "场景执行完成",
    outputs,
    task_results: taskResults
  };
}

function extractInterfaceConfig(task: Record<string, unknown>, index: number): InterfaceConfig {
  const interfaceValue = task.interface;
  if (!isRecord(interfaceValue)) {
    throw new HttpExecutionError(`第 ${index + 1} 个任务缺少 interface 配置`);
  }
  const method = String(interfaceValue.method ?? "").trim().toUpperCase();
  const url = String(interfaceValue.url ?? "").trim();
  if (!method) {
    throw new HttpExecutionError(`第 ${index + 1} 个任务的 interface.method 不能为空`);
  }
  if (!url) {
    throw new HttpExecutionError(`第 ${index + 1} 个任务的 interface.url 不能为空`);
  }
  const headersValue = interfaceValue.headers ?? {};
  if (!isRecord(headersValue)) {
    throw new HttpExecutionError(`第 ${index + 1} 个任务的 interface.headers 必须是对象`);
  }
  return {
    method,
    url,
    contentType: String(interfaceValue.contentType ?? "").trim(),
    headers: Object.fromEntries(Object.entries(headersValue).map(([key, value]) => [key, stringifyHeaderValue(value)])),
    query: isRecord(interfaceValue.query)
      ? structuredClone(interfaceValue.query)
      : isRecord(interfaceValue.queryParams)
        ? structuredClone(interfaceValue.queryParams)
        : {},
    params: structuredClone(interfaceValue.params),
    body: structuredClone(interfaceValue.body),
    json: structuredClone(interfaceValue.json)
  };
}

async function sendInterfaceRequest(interfaceConfig: InterfaceConfig, timeoutSec: number): Promise<Response> {
  const payload = interfaceConfig.json ?? interfaceConfig.body ?? interfaceConfig.params;
  const requestUrl = new URL(interfaceConfig.url);
  const query = interfaceConfig.query;
  if (!isRecord(query)) {
    throw new HttpExecutionError("interface.query 必须是对象");
  }
  for (const [key, value] of Object.entries(query)) {
    requestUrl.searchParams.set(key, stringifyBodyValue(value));
  }

  const headers = new Headers(interfaceConfig.headers);
  const init: RequestInit = {
    method: interfaceConfig.method,
    headers,
    redirect: "follow",
    signal: AbortSignal.timeout(Math.max(1, timeoutSec) * 1000)
  };

  const contentType = interfaceConfig.contentType.toLowerCase();
  if (contentType === "multipart/form-data") {
    const form = new FormData();
    const mapping = coerceMappingPayload(payload, "interface.params");
    for (const [key, value] of Object.entries(mapping)) {
      form.append(key, stringifyBodyValue(value));
    }
    init.body = form;
    headers.delete("content-type");
  } else if (contentType === "application/x-www-form-urlencoded") {
    const search = new URLSearchParams();
    const mapping = coerceMappingPayload(payload, "interface.params");
    for (const [key, value] of Object.entries(mapping)) {
      search.append(key, stringifyBodyValue(value));
    }
    init.body = search;
  } else if (contentType === "application/json") {
    init.body = JSON.stringify(payload);
    if (!headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
  } else if (payload !== undefined && payload !== null) {
    if (typeof payload === "object") {
      init.body = JSON.stringify(payload);
      if (!headers.has("Content-Type")) {
        headers.set("Content-Type", "application/json");
      }
    } else {
      init.body = stringifyBodyValue(payload);
    }
  }

  try {
    const response = await fetch(requestUrl, init);
    if (!response.ok) {
      throw new HttpExecutionError(`HTTP ${response.status}`);
    }
    return response;
  } catch (error) {
    if (error instanceof HttpExecutionError) {
      throw error;
    }
    const curlResponse = await sendInterfaceRequestWithCurl(interfaceConfig, requestUrl.toString(), payload);
    if (curlResponse.status >= 400) {
      throw new HttpExecutionError(`HTTP ${curlResponse.status}`);
    }
    return curlResponse;
  }
}

function applyInputBindings(
  task: Record<string, unknown>,
  bindings: VariableDefinition[],
  variables: Record<string, unknown>
) {
  for (const binding of bindings) {
    const targetPath = String(binding.target_path ?? "").trim();
    const expression = String(binding.expression ?? "").trim();
    if (!targetPath || !expression) {
      continue;
    }
    const resolved = resolveExpression(expression, variables);
    setByPath(task, targetPath, resolved);
  }
}

function resolveExpression(expression: string, outputs: Record<string, unknown>): unknown {
  const normalizedExpression = normalizeVariablePlaceholders(expression);
  const fullMatch = normalizedExpression.match(FULL_VARIABLE_PATTERN);
  if (fullMatch) {
    const variableName = fullMatch[1];
    if (!(variableName in outputs)) {
      throw new HttpExecutionError(`变量未定义：${variableName}`);
    }
    return structuredClone(outputs[variableName]);
  }
  return normalizedExpression.replace(VARIABLE_PATTERN, (_, variableName: string) => {
    if (!(variableName in outputs)) {
      throw new HttpExecutionError(`变量未定义：${variableName}`);
    }
    const value = outputs[variableName];
    if (value == null) {
      return "";
    }
    if (typeof value === "object") {
      return JSON.stringify(value);
    }
    return String(value);
  });
}

function extractOutputVariables(definitions: VariableDefinition[], responsePayload: Record<string, unknown>) {
  const produced: Record<string, unknown> = {};
  const body = responsePayload.body;
  const parsedRespMsg = parseRespMsg(body);
  const wrapper = {
    respMsg: parsedRespMsg === MISSING ? body : parsedRespMsg,
    response: body,
    status_code: responsePayload.status_code,
    headers: responsePayload.headers,
    body,
    text: responsePayload.text,
    url: responsePayload.url
  };
  for (const definition of definitions) {
    const name = String(definition.name ?? "").trim();
    const sourcePath = String(definition.source_path ?? "").trim();
    if (!name) {
      continue;
    }
    if (!sourcePath) {
      produced[name] = structuredClone(body);
      continue;
    }
    let value = getByPath(body, sourcePath);
    if (value === MISSING) {
      value = getByPath(wrapper, sourcePath);
    }
    if (value === MISSING) {
      throw new HttpExecutionError(`输出变量提取失败：${name} <- ${sourcePath}`);
    }
    produced[name] = structuredClone(value);
  }
  return produced;
}

function parseRespMsg(body: unknown): unknown | typeof MISSING {
  if (!isRecord(body) || typeof body.respMsg !== "string") {
    return MISSING;
  }
  try {
    return JSON.parse(body.respMsg);
  } catch {
    return MISSING;
  }
}

function ensureInterfaceVariablesResolved(interfaceConfig: InterfaceConfig) {
  const unresolved = [...collectUnresolvedVariables(interfaceConfig)].sort();
  if (unresolved.length > 0) {
    throw new HttpExecutionError(`缺少执行变量：${unresolved.join(", ")}`);
  }
}

function buildRuntimeDefaults(): Record<string, unknown> {
  const defaults: Record<string, unknown> = {
    cookie: env.GETRESULT_COOKIE,
    uid: env.GETRESULT_UID,
    addressId: env.GETRESULT_ADDRESS_ID,
    appointmentTime: env.GETRESULT_APPOINTMENT_TIME
  };
  return Object.fromEntries(Object.entries(defaults).filter(([, value]) => value !== undefined && value !== ""));
}

function applyKnownVariables(value: unknown, variables: Record<string, unknown>): unknown {
  if (typeof value === "string") {
    return resolveKnownVariables(value, variables);
  }
  if (Array.isArray(value)) {
    return value.map((item) => applyKnownVariables(item, variables));
  }
  if (isRecord(value)) {
    return Object.fromEntries(Object.entries(value).map(([key, nested]) => [key, applyKnownVariables(nested, variables)]));
  }
  return value;
}

function resolveKnownVariables(expression: string, variables: Record<string, unknown>): unknown {
  const normalizedExpression = normalizeVariablePlaceholders(expression);
  const fullMatch = normalizedExpression.match(FULL_VARIABLE_PATTERN);
  if (fullMatch) {
    const variableName = fullMatch[1];
    if (variableName in variables) {
      return structuredClone(variables[variableName]);
    }
    return normalizedExpression;
  }
  return normalizedExpression.replace(VARIABLE_PATTERN, (match, variableName: string) => {
    if (!(variableName in variables)) {
      return match;
    }
    const value = variables[variableName];
    if (value == null) {
      return "";
    }
    if (typeof value === "object") {
      return JSON.stringify(value);
    }
    return String(value);
  });
}

function normalizeVariablePlaceholders(expression: string) {
  return expression.replace(/\\\$\{/g, "${");
}

function collectUnresolvedVariables(value: unknown): Set<string> {
  const unresolved = new Set<string>();
  if (typeof value === "string") {
    for (const match of value.matchAll(VARIABLE_PATTERN)) {
      unresolved.add(match[1]);
    }
    return unresolved;
  }
  if (Array.isArray(value)) {
    for (const nested of value) {
      for (const key of collectUnresolvedVariables(nested)) {
        unresolved.add(key);
      }
    }
    return unresolved;
  }
  if (isRecord(value)) {
    for (const nested of Object.values(value)) {
      for (const key of collectUnresolvedVariables(nested)) {
        unresolved.add(key);
      }
    }
  }
  return unresolved;
}

async function buildResponsePayload(response: Response, fallbackUrl: string) {
  const text = await response.text();
  let body: unknown = text;
  try {
    body = JSON.parse(text);
  } catch {
    body = text;
  }
  return {
    status_code: response.status,
    headers: Object.fromEntries(response.headers.entries()),
    body,
    text,
    url: response.url || fallbackUrl
  };
}

function raiseForBusinessError(responsePayload: Record<string, unknown>) {
  const body = responsePayload.body;
  const url = String(responsePayload.url ?? "");
  const text = String(responsePayload.text ?? "");
  const parsedRespMsg = parseRespMsg(body);

  if (url.includes("zzsso.zhuanspirit.com/login") || text.includes("zzsso.zhuanspirit.com/login")) {
    throw new HttpExecutionError("接口调用失败：登录态已失效，需要重新登录后刷新 Cookie");
  }

  if (isRecord(body) && Number(body.status ?? 0) === -3) {
    const desc = String(body.desc ?? "调用接口错误").trim() || "调用接口错误";
    throw new HttpExecutionError(`接口调用失败：${desc}，可能是 Cookie 已失效，需要重新登录`);
  }

  if (isRecord(parsedRespMsg)) {
    const code = parsedRespMsg.code;
    if (typeof code === "number" && code !== 0) {
      const message = String(parsedRespMsg.errorMsg ?? parsedRespMsg.errMsg ?? parsedRespMsg.message ?? "").trim();
      if (message) {
        throw new HttpExecutionError(`接口业务失败：${message}`);
      }
      throw new HttpExecutionError(`接口业务失败：code=${code}`);
    }
  }
}

async function sendInterfaceRequestWithCurl(interfaceConfig: InterfaceConfig, url: string, payload: unknown): Promise<Response> {
  const command = [
    "-sS",
    "-L",
    "-X",
    interfaceConfig.method,
    url,
    "-D",
    "-",
    "--max-time",
    String(Math.max(1, env.SCENE_HTTP_TIMEOUT_SEC))
  ];

  for (const [key, value] of Object.entries(interfaceConfig.headers)) {
    command.push("-H", `${key}: ${value}`);
  }

  const contentType = interfaceConfig.contentType.toLowerCase();
  if (contentType === "application/json") {
    command.push("-H", "Content-Type: application/json", "--data-raw", JSON.stringify(payload));
  } else if (contentType === "application/x-www-form-urlencoded") {
    const mapping = coerceMappingPayload(payload, "interface.params");
    for (const [key, value] of Object.entries(mapping)) {
      command.push("--data-urlencode", `${key}=${stringifyBodyValue(value)}`);
    }
  } else if (contentType === "multipart/form-data") {
    const mapping = coerceMappingPayload(payload, "interface.params");
    for (const [key, value] of Object.entries(mapping)) {
      command.push("-F", `${key}=${stringifyBodyValue(value)}`);
    }
  } else if (payload != null) {
    command.push("--data-raw", stringifyBodyValue(payload));
  }

  const result = await execFileAsync("curl", command, { encoding: "utf8" });
  const rawOutput = result.stdout;
  const separator = rawOutput.includes("\r\n\r\n") ? "\r\n\r\n" : "\n\n";
  const parts = rawOutput.split(separator).filter((part) => part.trim());
  if (parts.length === 0) {
    throw new HttpExecutionError("curl 未返回任何响应");
  }
  const responseText = parts[parts.length - 1];
  let statusCode = 200;
  const headers = new Headers();
  const headerBlock = [...parts.slice(0, -1)].reverse().find((part) => part.trimStart().startsWith("HTTP/")) ?? "";
  if (headerBlock) {
    const headerLines = headerBlock.split(/\r?\n/).filter(Boolean);
    const match = headerLines[0]?.match(/HTTP\/\S+\s+(\d{3})/);
    if (match) {
      statusCode = Number(match[1]);
    }
    for (const line of headerLines.slice(1)) {
      const separatorIndex = line.indexOf(":");
      if (separatorIndex < 0) {
        continue;
      }
      headers.set(line.slice(0, separatorIndex).trim(), line.slice(separatorIndex + 1).trim());
    }
  }
  return new Response(responseText, {
    status: statusCode,
    headers
  });
}

function coerceMappingPayload(payload: unknown, fieldName: string): Record<string, unknown> {
  if (payload == null) {
    return {};
  }
  if (!isRecord(payload)) {
    throw new HttpExecutionError(`${fieldName} 必须是对象`);
  }
  return payload;
}

function stringifyBodyValue(value: unknown): string {
  if (value == null) {
    return "";
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function stringifyHeaderValue(value: unknown): string {
  return value == null ? "" : String(value);
}

function safeReadInterfaceField(task: Record<string, unknown>, key: string): string | null {
  if (!isRecord(task.interface)) {
    return null;
  }
  const value = task.interface[key];
  if (value == null) {
    return null;
  }
  const text = String(value).trim();
  return text || null;
}

function setByPath(root: Record<string, unknown>, path: string, value: unknown) {
  const segments = parsePath(path, "target_path");
  if (segments.length === 0) {
    throw new HttpExecutionError("变量 target_path 不能为空");
  }
  let current: unknown = root;
  for (let index = 0; index < segments.length - 1; index += 1) {
    const segment = segments[index];
    const nextSegment = segments[index + 1];
    const container: unknown = typeof nextSegment === "number" ? [] : {};
    if (typeof segment === "string") {
      if (!isRecord(current)) {
        throw new HttpExecutionError(`变量 target_path 非法：${path}`);
      }
      let nextValue = current[segment];
      if (!isRecord(nextValue) && !Array.isArray(nextValue)) {
        nextValue = structuredClone(container);
        current[segment] = nextValue;
      }
      current = nextValue;
      continue;
    }
    if (!Array.isArray(current) || segment < 0) {
      throw new HttpExecutionError(`变量 target_path 非法：${path}`);
    }
    while (current.length <= segment) {
      current.push(structuredClone(container));
    }
    let nextValue = current[segment];
    if (!isRecord(nextValue) && !Array.isArray(nextValue)) {
      nextValue = structuredClone(container);
      current[segment] = nextValue;
    }
    current = nextValue;
  }

  const lastSegment = segments[segments.length - 1];
  if (typeof lastSegment === "string") {
    if (!isRecord(current)) {
      throw new HttpExecutionError(`变量 target_path 非法：${path}`);
    }
    current[lastSegment] = value;
    return;
  }
  if (!Array.isArray(current) || lastSegment < 0) {
    throw new HttpExecutionError(`变量 target_path 非法：${path}`);
  }
  while (current.length <= lastSegment) {
    current.push(null);
  }
  current[lastSegment] = value;
}

function getByPath(root: unknown, path: string): unknown | typeof MISSING {
  let segments: Array<string | number>;
  try {
    segments = parsePath(path, "source_path");
  } catch {
    return MISSING;
  }
  let current = root;
  for (const segment of segments) {
    if (isRecord(current)) {
      if (typeof segment !== "string" || !(segment in current)) {
        return MISSING;
      }
      current = current[segment];
      continue;
    }
    if (Array.isArray(current)) {
      if (typeof segment !== "number" || segment < 0 || segment >= current.length) {
        return MISSING;
      }
      current = current[segment];
      continue;
    }
    return MISSING;
  }
  return current;
}

function parsePath(path: string, fieldName: string): Array<string | number> {
  const tokens: Array<string | number> = [];
  for (const rawSegment of path.split(".").filter(Boolean)) {
    let consumed = "";
    PATH_SEGMENT_PATTERN.lastIndex = 0;
    let match: RegExpExecArray | null;
    while ((match = PATH_SEGMENT_PATTERN.exec(rawSegment)) !== null) {
      consumed += match[0];
      if (match[1] != null) {
        tokens.push(match[1]);
      } else {
        tokens.push(Number(match[2]));
      }
    }
    if (consumed !== rawSegment) {
      throw new HttpExecutionError(`变量 ${fieldName} 非法：${path}`);
    }
  }
  return tokens;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}
