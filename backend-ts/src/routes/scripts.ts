import type { FastifyInstance } from "fastify";

import { env } from "../config.js";
import { prisma } from "../db/prisma.js";
import { badRequest, notFound, sendError } from "../lib/errors.js";
import { serializeDate } from "../lib/serializers.js";
import { AndroidExecutionError, executeCompiledScene } from "../modules/midscene/index.js";
import {
  compileSceneScript,
  dumpTaskSnapshot,
  extractScriptEnv,
  parseScriptTasks,
  SceneCompileError
} from "../services/scene-compiler.js";
import { scriptCreateSchema, scriptUpdateSchema } from "../schemas.js";

function serializeScriptRead(script: {
  id: number;
  name: string;
  content: string;
  source_type: string;
  created_at: Date;
  updated_at: Date;
  scene_count?: number;
  scenes?: Array<{ id: number; name: string }>;
}) {
  return {
    id: script.id,
    name: script.name,
    content: script.content,
    source_type: script.source_type,
    created_at: serializeDate(script.created_at),
    updated_at: serializeDate(script.updated_at),
    scene_count: script.scene_count ?? 0,
    scenes: script.scenes ?? []
  };
}

async function scriptSceneReferences(scriptId: number) {
  return prisma.scene.findMany({
    where: {
      sceneScripts: {
        some: {
          script_id: scriptId
        }
      }
    },
    select: {
      id: true,
      name: true
    }
  });
}

export async function registerScriptRoutes(app: FastifyInstance): Promise<void> {
  app.get("/api/scripts", async (_request, reply) => {
    try {
      const scripts = await prisma.script.findMany({
        orderBy: {
          updated_at: "desc"
        },
        include: {
          _count: {
            select: {
              sceneScripts: true
            }
          }
        }
      });
      return scripts.map((script) =>
        serializeScriptRead({
          ...script,
          scene_count: script._count.sceneScripts,
          scenes: []
        })
      );
    } catch (error) {
      return sendError(reply, error);
    }
  });

  app.get("/api/scripts/:scriptId", async (request, reply) => {
    try {
      const scriptId = Number((request.params as { scriptId: string }).scriptId);
      const script = await prisma.script.findUnique({ where: { id: scriptId } });
      if (!script) {
        notFound("Script not found");
      }
      const [sceneCount, scenes] = await Promise.all([
        prisma.sceneScript.count({ where: { script_id: scriptId } }),
        scriptSceneReferences(scriptId)
      ]);
      return serializeScriptRead({
        ...script,
        scene_count: sceneCount,
        scenes
      });
    } catch (error) {
      return sendError(reply, error);
    }
  });

  app.get("/api/scripts/:scriptId/tasks", async (request, reply) => {
    try {
      const scriptId = Number((request.params as { scriptId: string }).scriptId);
      const script = await prisma.script.findUnique({ where: { id: scriptId } });
      if (!script) {
        notFound("Script not found");
      }
      return parseScriptTasks(script.content).map((item) => ({
        script_id: script.id,
        task_index: item.task_index,
        task_name: item.task_name,
        continue_on_error: item.continue_on_error,
        task_content: dumpTaskSnapshot(item.task)
      }));
    } catch (error) {
      if (error instanceof SceneCompileError) {
        return reply.code(400).send({ detail: error.message });
      }
      return sendError(reply, error);
    }
  });

  app.post("/api/scripts", async (request, reply) => {
    try {
      const payload = scriptCreateSchema.parse(request.body);
      const script = await prisma.$transaction(async (tx) => {
        const created = await tx.script.create({
          data: {
            name: payload.name,
            content: payload.content,
            source_type: payload.source_type
          }
        });
        await tx.scriptVersion.create({
          data: {
            script_id: created.id,
            version_no: 1,
            content: created.content
          }
        });
        return created;
      });
      return reply.code(201).send(
        serializeScriptRead({
          ...script,
          scene_count: 0,
          scenes: []
        })
      );
    } catch (error) {
      return sendError(reply, error);
    }
  });

  app.put("/api/scripts/:scriptId", async (request, reply) => {
    try {
      const scriptId = Number((request.params as { scriptId: string }).scriptId);
      const payload = scriptUpdateSchema.parse(request.body);
      const existing = await prisma.script.findUnique({ where: { id: scriptId } });
      if (!existing) {
        notFound("Script not found");
      }
      const script = await prisma.$transaction(async (tx) => {
        const updated = await tx.script.update({
          where: { id: scriptId },
          data: {
            name: payload.name ?? existing.name,
            content: payload.content ?? existing.content,
            source_type: payload.source_type ?? existing.source_type
          }
        });
        const currentVersion = await tx.scriptVersion.aggregate({
          where: { script_id: scriptId },
          _max: { version_no: true }
        });
        await tx.scriptVersion.create({
          data: {
            script_id: updated.id,
            version_no: (currentVersion._max.version_no ?? 0) + 1,
            content: updated.content
          }
        });
        return updated;
      });
      const [sceneCount, scenes] = await Promise.all([
        prisma.sceneScript.count({ where: { script_id: scriptId } }),
        scriptSceneReferences(scriptId)
      ]);
      return serializeScriptRead({
        ...script,
        scene_count: sceneCount,
        scenes
      });
    } catch (error) {
      return sendError(reply, error);
    }
  });

  app.delete("/api/scripts/:scriptId", async (request, reply) => {
    try {
      const scriptId = Number((request.params as { scriptId: string }).scriptId);
      const existing = await prisma.script.findUnique({ where: { id: scriptId } });
      if (!existing) {
        notFound("Script not found");
      }
      await prisma.script.delete({ where: { id: scriptId } });
      return reply.code(204).send();
    } catch (error) {
      return sendError(reply, error);
    }
  });

  app.post("/api/scripts/:scriptId/copy", async (request, reply) => {
    try {
      const scriptId = Number((request.params as { scriptId: string }).scriptId);
      const existing = await prisma.script.findUnique({ where: { id: scriptId } });
      if (!existing) {
        notFound("Script not found");
      }
      const copied = await prisma.$transaction(async (tx) => {
        const script = await tx.script.create({
          data: {
            name: `${existing.name}-copy`,
            content: existing.content,
            source_type: existing.source_type
          }
        });
        await tx.scriptVersion.create({
          data: {
            script_id: script.id,
            version_no: 1,
            content: script.content
          }
        });
        return script;
      });
      return reply.code(201).send(
        serializeScriptRead({
          ...copied,
          scene_count: 0,
          scenes: []
        })
      );
    } catch (error) {
      return sendError(reply, error);
    }
  });

  // 单脚本直接执行：内存编译脚本为 YAML 后调 Midscene 执行，不创建临时 scene
  app.post("/api/scripts/:scriptId/execute", async (request, reply) => {
    try {
      const scriptId = Number((request.params as { scriptId: string }).scriptId);
      const script = await prisma.script.findUnique({ where: { id: scriptId } });
      if (!script) {
        notFound("Script not found");
      }
      // 解析脚本内容为环境段 + task 快照，再合成可执行 YAML
      const scriptEnv = extractScriptEnv(script.content);
      // 纯 UI app 脚本（无平台段、无 http interface 配置）默认按安卓执行，自动补 android 段
      const hasPlatformEnv = ["android", "ios", "web", "computer"].some(
        (key) => scriptEnv[key] !== undefined
      );
      const hasHttpInterface = /^\s*interface\s*:/m.test(script.content);
      if (!hasPlatformEnv && !hasHttpInterface) {
        scriptEnv.android = scriptEnv.android ?? {};
      }
      const tasks = parseScriptTasks(script.content);
      const taskSnapshots = tasks.map((item) => dumpTaskSnapshot(item.task));
      const compiledYaml = compileSceneScript(scriptEnv, taskSnapshots);

      const execution = await executeCompiledScene({
        compiledYaml,
        taskSnapshots,
        httpTimeoutSec: env.SCENE_HTTP_TIMEOUT_SEC,
        defaultAndroidDeviceId: env.MIDSCENE_ANDROID_DEVICE_ID
      });

      return {
        script_id: script.id,
        script_name: script.name,
        task_count: tasks.length,
        success: Boolean(execution.success),
        message: String(execution.message),
        outputs: execution.outputs,
        detail: {
          task_results: execution.task_results,
          result: execution.result ?? execution.outputs
        }
      };
    } catch (error) {
      if (error instanceof SceneCompileError) {
        return reply.code(400).send({ detail: error.message });
      }
      if (error instanceof AndroidExecutionError) {
        badRequest(error.message);
      }
      return sendError(reply, error);
    }
  });
}
