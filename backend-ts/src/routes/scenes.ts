import type { Scene, SceneScript, SceneTaskItem, Script } from "@prisma/client";
import type { FastifyInstance } from "fastify";

import { env } from "../config.js";
import { prisma } from "../db/prisma.js";
import { badRequest, conflict, notFound, sendError } from "../lib/errors.js";
import { serializeDate } from "../lib/serializers.js";
import {
  applyTaskVariableMeta,
  compileSceneScript,
  dumpTaskSnapshot,
  extractScriptEnv,
  findScriptTask,
  loadTaskSnapshot,
  mergeTaskVariableMeta,
  parseScriptTasks,
  SceneCompileError,
  sceneTaskSyncStatus,
  taskSnapshotKey,
  taskSnapshotVariableMeta
} from "../services/scene-compiler.js";
import { executeSceneHttpTasks, HttpExecutionError } from "../services/http-executor.js";
import {
  sceneCreateSchema,
  sceneScriptCreateSchema,
  sceneScriptUpdateSchema,
  sceneTaskItemCreateSchema,
  sceneTaskItemUpdateSchema,
  sceneUpdateSchema
} from "../schemas.js";

function serializeScriptRead(script: Script & { scene_count?: number }) {
  return {
    id: script.id,
    name: script.name,
    content: script.content,
    source_type: script.source_type,
    created_at: serializeDate(script.created_at),
    updated_at: serializeDate(script.updated_at),
    scene_count: script.scene_count ?? 0,
    scenes: []
  };
}

function serializeScene(scene: Scene, scriptCount = 0) {
  return {
    id: scene.id,
    name: scene.name,
    description: scene.description,
    source_type: scene.source_type,
    created_at: serializeDate(scene.created_at),
    updated_at: serializeDate(scene.updated_at),
    script_count: scriptCount
  };
}

async function getSceneOr404(sceneId: number) {
  const scene = await prisma.scene.findUnique({ where: { id: sceneId } });
  if (!scene) {
    notFound("Scene not found");
  }
  return scene;
}

async function getRelationOr404(sceneId: number, relationId: number) {
  const relation = await prisma.sceneScript.findUnique({ where: { id: relationId } });
  if (!relation || relation.scene_id !== sceneId) {
    notFound("Scene script relation not found");
  }
  return relation;
}

async function nextSortOrder(sceneId: number) {
  const currentMax = await prisma.sceneScript.aggregate({
    where: { scene_id: sceneId },
    _max: { sort_order: true }
  });
  return (currentMax._max.sort_order ?? 0) + 1;
}

async function nextTaskSortOrder(sceneId: number) {
  const currentMax = await prisma.sceneTaskItem.aggregate({
    where: { scene_id: sceneId },
    _max: { sort_order: true }
  });
  return (currentMax._max.sort_order ?? 0) + 1;
}

async function scriptReadPayload(script: Script) {
  const sceneCount = await prisma.sceneScript.count({ where: { script_id: script.id } });
  return serializeScriptRead({ ...script, scene_count: sceneCount });
}

async function serializeSceneTaskItem(taskItem: SceneTaskItem, script: Script) {
  const [syncStatus, syncMessage] = sceneTaskSyncStatus({
    scriptContent: script.content,
    taskIndex: taskItem.task_index,
    taskNameSnapshot: taskItem.task_name_snapshot,
    taskContentSnapshot: taskItem.task_content_snapshot
  });
  const variableMeta = taskSnapshotVariableMeta(taskItem.task_content_snapshot);
  return {
    id: taskItem.id,
    scene_id: taskItem.scene_id,
    script_id: taskItem.script_id,
    scene_script_id: taskItem.scene_script_id,
    task_index: taskItem.task_index,
    task_name_snapshot: taskItem.task_name_snapshot,
    task_content_snapshot: taskItem.task_content_snapshot,
    sort_order: taskItem.sort_order,
    remark: taskItem.remark,
    created_at: serializeDate(taskItem.created_at),
    sync_status: syncStatus,
    sync_message: syncMessage,
    input_bindings: variableMeta.inputs,
    output_variables: variableMeta.outputs,
    script: await scriptReadPayload(script)
  };
}

async function sceneTaskItems(sceneId: number) {
  const items = await prisma.sceneTaskItem.findMany({
    where: { scene_id: sceneId },
    orderBy: [{ sort_order: "asc" }, { id: "asc" }]
  });
  const scriptIds = [...new Set(items.map((item) => item.script_id))];
  const scripts = scriptIds.length
    ? await prisma.script.findMany({
        where: { id: { in: scriptIds } }
      })
    : [];
  const scriptMap = new Map(scripts.map((script) => [script.id, script]));
  const payload = [];
  for (const item of items) {
    const script = scriptMap.get(item.script_id);
    if (!script) {
      continue;
    }
    payload.push(await serializeSceneTaskItem(item, script));
  }
  return payload;
}

async function compiledSceneScript(scene: Scene) {
  const taskItems = await prisma.sceneTaskItem.findMany({
    where: { scene_id: scene.id },
    orderBy: [{ sort_order: "asc" }, { id: "asc" }]
  });
  if (taskItems.length === 0) {
    badRequest("Scene has no task items");
  }
  const firstScript = await prisma.script.findUnique({ where: { id: taskItems[0].script_id } });
  if (!firstScript) {
    badRequest("Scene task source script not found");
  }
  try {
    return {
      scene_id: scene.id,
      script_count: new Set(taskItems.map((item) => item.script_id)).size,
      task_count: taskItems.length,
      yaml: compileSceneScript(
        extractScriptEnv(firstScript.content),
        taskItems.map((item) => item.task_content_snapshot)
      )
    };
  } catch (error) {
    if (error instanceof SceneCompileError) {
      badRequest(error.message);
    }
    throw error;
  }
}

async function buildSceneDetail(scene: Scene) {
  const [scriptCount, relations] = await Promise.all([
    prisma.sceneScript.count({ where: { scene_id: scene.id } }),
    prisma.sceneScript.findMany({
      where: { scene_id: scene.id },
      orderBy: [{ sort_order: "asc" }, { id: "asc" }]
    })
  ]);
  const scriptIds = relations.map((relation) => relation.script_id);
  const scripts = scriptIds.length
    ? await prisma.script.findMany({
        where: { id: { in: scriptIds } }
      })
    : [];
  const scriptMap = new Map(scripts.map((script) => [script.id, script]));

  const relationPayload = [];
  for (const relation of relations) {
    const script = scriptMap.get(relation.script_id);
    if (!script) {
      continue;
    }
    relationPayload.push({
      id: relation.id,
      scene_id: relation.scene_id,
      script_id: relation.script_id,
      sort_order: relation.sort_order,
      remark: relation.remark,
      created_at: serializeDate(relation.created_at),
      script: await scriptReadPayload(script)
    });
  }

  return {
    ...serializeScene(scene, scriptCount),
    scripts: relationPayload,
    task_items: await sceneTaskItems(scene.id)
  };
}

async function executeScene(scene: Scene, compiled: { script_count: number; task_count: number }) {
  try {
    const taskItems = await prisma.sceneTaskItem.findMany({
      where: { scene_id: scene.id },
      orderBy: [{ sort_order: "asc" }, { id: "asc" }]
    });
    const execution = await executeSceneHttpTasks({
      taskSnapshots: taskItems.map((item) => item.task_content_snapshot),
      timeoutSec: env.SCENE_HTTP_TIMEOUT_SEC
    });
    return {
      scene_id: scene.id,
      scene_name: scene.name,
      script_count: compiled.script_count,
      task_count: compiled.task_count,
      success: Boolean(execution.success),
      message: String(execution.message),
      outputs: execution.outputs,
      detail: {
        task_results: execution.task_results
      }
    };
  } catch (error) {
    if (error instanceof HttpExecutionError) {
      badRequest(error.message);
    }
    throw error;
  }
}

export async function registerSceneRoutes(app: FastifyInstance): Promise<void> {
  app.get("/api/scenes", async (_request, reply) => {
    try {
      const scenes = await prisma.scene.findMany({
        orderBy: { updated_at: "desc" },
        include: {
          _count: {
            select: {
              sceneScripts: true
            }
          }
        }
      });
      return scenes.map((scene) => serializeScene(scene, scene._count.sceneScripts));
    } catch (error) {
      return sendError(reply, error);
    }
  });

  app.post("/api/scenes", async (request, reply) => {
    try {
      const payload = sceneCreateSchema.parse(request.body);
      const scene = await prisma.scene.create({
        data: {
          name: payload.name,
          description: payload.description,
          source_type: payload.source_type
        }
      });
      return reply.code(201).send(serializeScene(scene, 0));
    } catch (error) {
      return sendError(reply, error);
    }
  });

  app.post("/api/scenes/:sceneId/copy", async (request, reply) => {
    try {
      const sceneId = Number((request.params as { sceneId: string }).sceneId);
      const origin = await getSceneOr404(sceneId);
      const copied = await prisma.$transaction(async (tx) => {
        const nextScene = await tx.scene.create({
          data: {
            name: `${origin.name}-copy`,
            description: origin.description,
            source_type: origin.source_type
          }
        });

        const originRelations = await tx.sceneScript.findMany({
          where: { scene_id: sceneId },
          orderBy: [{ sort_order: "asc" }, { id: "asc" }]
        });
        const copiedRelationIdsByScript = new Map<number, number[]>();
        for (const relation of originRelations) {
          const copiedRelation = await tx.sceneScript.create({
            data: {
              scene_id: nextScene.id,
              script_id: relation.script_id,
              sort_order: relation.sort_order,
              remark: relation.remark
            }
          });
          copiedRelationIdsByScript.set(relation.script_id, [
            ...(copiedRelationIdsByScript.get(relation.script_id) ?? []),
            copiedRelation.id
          ]);
        }

        const originTaskItems = await tx.sceneTaskItem.findMany({
          where: { scene_id: sceneId },
          orderBy: [{ sort_order: "asc" }, { id: "asc" }]
        });
        for (const item of originTaskItems) {
          const relationIds = copiedRelationIdsByScript.get(item.script_id) ?? [];
          const copiedSceneScriptId = relationIds.shift() ?? null;
          copiedRelationIdsByScript.set(item.script_id, relationIds);
          await tx.sceneTaskItem.create({
            data: {
              scene_id: nextScene.id,
              script_id: item.script_id,
              scene_script_id: copiedSceneScriptId,
              task_index: item.task_index,
              task_name_snapshot: item.task_name_snapshot,
              task_content_snapshot: item.task_content_snapshot,
              sort_order: item.sort_order,
              remark: item.remark
            }
          });
        }

        return nextScene;
      });
      return reply.code(201).send(await buildSceneDetail(copied));
    } catch (error) {
      return sendError(reply, error);
    }
  });

  app.get("/api/scenes/:sceneId", async (request, reply) => {
    try {
      const sceneId = Number((request.params as { sceneId: string }).sceneId);
      const scene = await getSceneOr404(sceneId);
      return buildSceneDetail(scene);
    } catch (error) {
      return sendError(reply, error);
    }
  });

  app.put("/api/scenes/:sceneId", async (request, reply) => {
    try {
      const sceneId = Number((request.params as { sceneId: string }).sceneId);
      const payload = sceneUpdateSchema.parse(request.body);
      const scene = await getSceneOr404(sceneId);
      const updated = await prisma.scene.update({
        where: { id: scene.id },
        data: {
          name: payload.name ?? scene.name,
          description: payload.description ?? scene.description,
          source_type: payload.source_type ?? scene.source_type
        }
      });
      const scriptCount = await prisma.sceneScript.count({ where: { scene_id: updated.id } });
      return serializeScene(updated, scriptCount);
    } catch (error) {
      return sendError(reply, error);
    }
  });

  app.delete("/api/scenes/:sceneId", async (request, reply) => {
    try {
      const sceneId = Number((request.params as { sceneId: string }).sceneId);
      await getSceneOr404(sceneId);
      await prisma.scene.delete({ where: { id: sceneId } });
      return reply.code(204).send();
    } catch (error) {
      return sendError(reply, error);
    }
  });

  app.post("/api/scenes/:sceneId/scripts", async (request, reply) => {
    try {
      const sceneId = Number((request.params as { sceneId: string }).sceneId);
      const payload = sceneScriptCreateSchema.parse(request.body);
      await getSceneOr404(sceneId);
      const script = await prisma.script.findUnique({ where: { id: payload.script_id } });
      if (!script) {
        notFound("Script not found");
      }
      const existingRelation = await prisma.sceneScript.findFirst({
        where: {
          scene_id: sceneId,
          script_id: payload.script_id
        }
      });
      if (existingRelation) {
        badRequest("Script already added to scene");
      }
      const relation = await prisma.sceneScript.create({
        data: {
          scene_id: sceneId,
          script_id: payload.script_id,
          sort_order: payload.sort_order ?? (await nextSortOrder(sceneId)),
          remark: payload.remark
        }
      });
      return reply.code(201).send({
        id: relation.id,
        scene_id: relation.scene_id,
        script_id: relation.script_id,
        sort_order: relation.sort_order,
        remark: relation.remark,
        created_at: serializeDate(relation.created_at),
        script: await scriptReadPayload(script)
      });
    } catch (error) {
      return sendError(reply, error);
    }
  });

  app.put("/api/scenes/:sceneId/scripts/:relationId", async (request, reply) => {
    try {
      const { sceneId, relationId } = request.params as { sceneId: string; relationId: string };
      const payload = sceneScriptUpdateSchema.parse(request.body);
      const relation = await getRelationOr404(Number(sceneId), Number(relationId));
      const updated = await prisma.sceneScript.update({
        where: { id: relation.id },
        data: {
          sort_order: payload.sort_order ?? relation.sort_order,
          remark: payload.remark ?? relation.remark
        }
      });
      const script = await prisma.script.findUnique({ where: { id: updated.script_id } });
      if (!script) {
        notFound("Script not found");
      }
      return {
        id: updated.id,
        scene_id: updated.scene_id,
        script_id: updated.script_id,
        sort_order: updated.sort_order,
        remark: updated.remark,
        created_at: serializeDate(updated.created_at),
        script: await scriptReadPayload(script)
      };
    } catch (error) {
      return sendError(reply, error);
    }
  });

  app.delete("/api/scenes/:sceneId/scripts/:relationId", async (request, reply) => {
    try {
      const { sceneId, relationId } = request.params as { sceneId: string; relationId: string };
      const relation = await getRelationOr404(Number(sceneId), Number(relationId));
      await prisma.$transaction(async (tx) => {
        await tx.sceneTaskItem.deleteMany({ where: { scene_script_id: relation.id } });
        await tx.sceneScript.delete({ where: { id: relation.id } });
      });
      return reply.code(204).send();
    } catch (error) {
      return sendError(reply, error);
    }
  });

  app.get("/api/scenes/:sceneId/task-items", async (request, reply) => {
    try {
      const sceneId = Number((request.params as { sceneId: string }).sceneId);
      await getSceneOr404(sceneId);
      return sceneTaskItems(sceneId);
    } catch (error) {
      return sendError(reply, error);
    }
  });

  app.post("/api/scenes/:sceneId/task-items", async (request, reply) => {
    try {
      const sceneId = Number((request.params as { sceneId: string }).sceneId);
      const payload = sceneTaskItemCreateSchema.parse(request.body);
      await getSceneOr404(sceneId);
      const script = await prisma.script.findUnique({ where: { id: payload.script_id } });
      if (!script) {
        notFound("Script not found");
      }
      let taskList;
      try {
        taskList = parseScriptTasks(script.content);
      } catch (error) {
        if (error instanceof SceneCompileError) {
          badRequest(error.message);
        }
        throw error;
      }
      const matchedTask = taskList.find((item) => item.task_index === payload.task_index);
      if (!matchedTask) {
        notFound("Task not found in script");
      }
      const sceneScript = await prisma.sceneScript.findFirst({
        where: {
          scene_id: sceneId,
          script_id: payload.script_id
        }
      });
      const taskItem = await prisma.sceneTaskItem.create({
        data: {
          scene_id: sceneId,
          script_id: payload.script_id,
          scene_script_id: sceneScript?.id ?? null,
          task_index: payload.task_index,
          task_name_snapshot: matchedTask.task_name,
          task_content_snapshot: dumpTaskSnapshot(matchedTask.task),
          sort_order: await nextTaskSortOrder(sceneId),
          remark: payload.remark
        }
      });
      return reply.code(201).send(await serializeSceneTaskItem(taskItem, script));
    } catch (error) {
      return sendError(reply, error);
    }
  });

  app.put("/api/scenes/:sceneId/task-items/:itemId", async (request, reply) => {
    try {
      const { sceneId, itemId } = request.params as { sceneId: string; itemId: string };
      const payload = sceneTaskItemUpdateSchema.parse(request.body);
      const taskItem = await prisma.sceneTaskItem.findUnique({ where: { id: Number(itemId) } });
      if (!taskItem || taskItem.scene_id !== Number(sceneId)) {
        notFound("Scene task item not found");
      }
      const script = await prisma.script.findUnique({ where: { id: taskItem.script_id } });
      if (!script) {
        notFound("Script not found");
      }
      let taskContentSnapshot = taskItem.task_content_snapshot;
      if (payload.input_bindings !== undefined || payload.output_variables !== undefined) {
        const currentMeta = taskSnapshotVariableMeta(taskItem.task_content_snapshot);
        const nextTask = applyTaskVariableMeta(loadTaskSnapshot(taskItem.task_content_snapshot), {
          inputBindings: payload.input_bindings ?? currentMeta.inputs,
          outputVariables: payload.output_variables ?? currentMeta.outputs
        });
        taskContentSnapshot = dumpTaskSnapshot(nextTask);
      }
      const updated = await prisma.sceneTaskItem.update({
        where: { id: taskItem.id },
        data: {
          sort_order: payload.sort_order ?? taskItem.sort_order,
          remark: payload.remark ?? taskItem.remark,
          task_content_snapshot: taskContentSnapshot
        }
      });
      return serializeSceneTaskItem(updated, script);
    } catch (error) {
      return sendError(reply, error);
    }
  });

  app.delete("/api/scenes/:sceneId/task-items/:itemId", async (request, reply) => {
    try {
      const { sceneId, itemId } = request.params as { sceneId: string; itemId: string };
      const taskItem = await prisma.sceneTaskItem.findUnique({ where: { id: Number(itemId) } });
      if (!taskItem || taskItem.scene_id !== Number(sceneId)) {
        notFound("Scene task item not found");
      }
      await prisma.sceneTaskItem.delete({ where: { id: taskItem.id } });
      return reply.code(204).send();
    } catch (error) {
      return sendError(reply, error);
    }
  });

  app.post("/api/scenes/:sceneId/task-items/:itemId/sync", async (request, reply) => {
    try {
      const { sceneId, itemId } = request.params as { sceneId: string; itemId: string };
      const taskItem = await prisma.sceneTaskItem.findUnique({ where: { id: Number(itemId) } });
      if (!taskItem || taskItem.scene_id !== Number(sceneId)) {
        notFound("Scene task item not found");
      }
      const script = await prisma.script.findUnique({ where: { id: taskItem.script_id } });
      if (!script) {
        notFound("Script not found");
      }
      const matchedTask = findScriptTask(script.content, taskItem.task_index);
      if (!matchedTask) {
        conflict("Task not found in current script");
      }
      const currentMeta = taskSnapshotVariableMeta(taskItem.task_content_snapshot);
      const updated = await prisma.sceneTaskItem.update({
        where: { id: taskItem.id },
        data: {
          task_name_snapshot: matchedTask.task_name,
          task_content_snapshot: dumpTaskSnapshot(
            mergeTaskVariableMeta(matchedTask.task, {
              inputBindings: currentMeta.inputs,
              outputVariables: currentMeta.outputs
            })
          )
        }
      });
      return serializeSceneTaskItem(updated, script);
    } catch (error) {
      return sendError(reply, error);
    }
  });

  app.post("/api/scenes/:sceneId/task-items/sync", async (request, reply) => {
    try {
      const sceneId = Number((request.params as { sceneId: string }).sceneId);
      await getSceneOr404(sceneId);
      const items = await prisma.sceneTaskItem.findMany({
        where: { scene_id: sceneId },
        orderBy: [{ sort_order: "asc" }, { id: "asc" }]
      });
      if (items.length === 0) {
        return {
          updated_count: 0,
          missing_count: 0,
          task_items: []
        };
      }

      const scriptIds = [...new Set(items.map((item) => item.script_id))];
      const scripts = await prisma.script.findMany({ where: { id: { in: scriptIds } } });
      const scriptMap = new Map(scripts.map((script) => [script.id, script]));

      let updatedCount = 0;
      let missingCount = 0;
      for (const item of items) {
        const script = scriptMap.get(item.script_id);
        if (!script) {
          missingCount += 1;
          continue;
        }
        const matchedTask = findScriptTask(script.content, item.task_index);
        if (!matchedTask) {
          missingCount += 1;
          continue;
        }
        const currentMeta = taskSnapshotVariableMeta(item.task_content_snapshot);
        const nextSnapshot = dumpTaskSnapshot(
          mergeTaskVariableMeta(matchedTask.task, {
            inputBindings: currentMeta.inputs,
            outputVariables: currentMeta.outputs
          })
        );
        if (
          matchedTask.task_name === item.task_name_snapshot &&
          taskSnapshotKey(nextSnapshot) === taskSnapshotKey(item.task_content_snapshot)
        ) {
          continue;
        }
        await prisma.sceneTaskItem.update({
          where: { id: item.id },
          data: {
            task_name_snapshot: matchedTask.task_name,
            task_content_snapshot: nextSnapshot
          }
        });
        updatedCount += 1;
      }

      return {
        updated_count: updatedCount,
        missing_count: missingCount,
        task_items: await sceneTaskItems(sceneId)
      };
    } catch (error) {
      return sendError(reply, error);
    }
  });

  app.get("/api/scenes/:sceneId/compiled-script", async (request, reply) => {
    try {
      const sceneId = Number((request.params as { sceneId: string }).sceneId);
      const scene = await getSceneOr404(sceneId);
      return compiledSceneScript(scene);
    } catch (error) {
      return sendError(reply, error);
    }
  });

  app.post("/api/scenes/:sceneId/execute", async (request, reply) => {
    try {
      const sceneId = Number((request.params as { sceneId: string }).sceneId);
      const scene = await getSceneOr404(sceneId);
      const compiled = await compiledSceneScript(scene);
      return executeScene(scene, compiled);
    } catch (error) {
      return sendError(reply, error);
    }
  });
}
