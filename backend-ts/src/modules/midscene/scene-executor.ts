import { extractScriptEnv } from "../../services/scene-compiler.js";
import { executeSceneHttpTasks } from "../../services/http-executor.js";
import { executeSceneAndroidYaml } from "./android-executor.js";
import type { SceneExecutionResult } from "./types.js";

type SceneExecutorDeps = {
  executeHttp?: typeof executeSceneHttpTasks;
  executeAndroid?: typeof executeSceneAndroidYaml;
};

export async function executeCompiledScene(
  params: {
    compiledYaml: string;
    taskSnapshots: string[];
    httpTimeoutSec: number;
    defaultAndroidDeviceId?: string;
  },
  deps: SceneExecutorDeps = {}
): Promise<SceneExecutionResult> {
  const executeHttp = deps.executeHttp ?? executeSceneHttpTasks;
  const executeAndroid = deps.executeAndroid ?? executeSceneAndroidYaml;
  const scriptEnv = extractScriptEnv(params.compiledYaml);

  if (scriptEnv.android !== undefined) {
    return executeAndroid({
      yamlContent: params.compiledYaml,
      defaultDeviceId: params.defaultAndroidDeviceId
    });
  }

  return executeHttp({
    taskSnapshots: params.taskSnapshots,
    timeoutSec: params.httpTimeoutSec
  });
}
