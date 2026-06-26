import { z } from "zod";

const nonEmptyString = z.string().trim().min(1);

export const scriptCreateSchema = z.object({
  name: nonEmptyString.max(128),
  content: nonEmptyString,
  source_type: z.string().default("manual")
});

export const scriptUpdateSchema = z.object({
  name: nonEmptyString.max(128).optional(),
  content: nonEmptyString.optional(),
  source_type: z.string().optional()
});

// 执行脚本请求体：deviceId 可选，用于云端/云真机场景显式指定目标安卓设备
// （形如 host:port 的网络地址，服务端会在执行前负责 adb connect）。
// 不传则沿用 env.MIDSCENE_ANDROID_DEVICE_ID 或由 Midscene 自动选择，向后兼容。
export const scriptExecuteSchema = z.object({
  deviceId: nonEmptyString.optional()
});

export const sceneCreateSchema = z.object({
  name: nonEmptyString.max(128),
  description: z.string().default(""),
  source_type: z.string().default("manual")
});

export const sceneUpdateSchema = z.object({
  name: nonEmptyString.max(128).optional(),
  description: z.string().optional(),
  source_type: z.string().optional()
});

export const sceneScriptCreateSchema = z.object({
  script_id: z.number().int().positive(),
  sort_order: z.number().int().min(1).optional(),
  remark: z.string().default("")
});

export const sceneScriptUpdateSchema = z.object({
  sort_order: z.number().int().min(1).optional(),
  remark: z.string().optional()
});

export const sceneTaskInputBindingSchema = z.object({
  target_path: nonEmptyString.max(512),
  expression: nonEmptyString.max(512),
  description: z.string().max(255).default("")
});

export const sceneTaskOutputVariableSchema = z.object({
  name: nonEmptyString.max(128),
  source_path: z.string().max(512).default(""),
  description: z.string().max(255).default("")
});

export const sceneTaskItemCreateSchema = z.object({
  script_id: z.number().int().positive(),
  task_index: z.number().int().min(0),
  remark: z.string().default("")
});

export const sceneTaskItemUpdateSchema = z.object({
  sort_order: z.number().int().min(1).optional(),
  remark: z.string().optional(),
  input_bindings: z.array(sceneTaskInputBindingSchema).optional(),
  output_variables: z.array(sceneTaskOutputVariableSchema).optional()
});

export type ScriptCreateInput = z.infer<typeof scriptCreateSchema>;
export type ScriptUpdateInput = z.infer<typeof scriptUpdateSchema>;
export type ScriptExecuteInput = z.infer<typeof scriptExecuteSchema>;
export type SceneCreateInput = z.infer<typeof sceneCreateSchema>;
export type SceneUpdateInput = z.infer<typeof sceneUpdateSchema>;
export type SceneScriptCreateInput = z.infer<typeof sceneScriptCreateSchema>;
export type SceneScriptUpdateInput = z.infer<typeof sceneScriptUpdateSchema>;
export type SceneTaskItemCreateInput = z.infer<typeof sceneTaskItemCreateSchema>;
export type SceneTaskItemUpdateInput = z.infer<typeof sceneTaskItemUpdateSchema>;
export type SceneTaskInputBindingInput = z.infer<typeof sceneTaskInputBindingSchema>;
export type SceneTaskOutputVariableInput = z.infer<typeof sceneTaskOutputVariableSchema>;
