import { http } from './client';
import type { Script } from './scripts';

export type Scene = {
  id: number;
  name: string;
  description: string;
  source_type: string;
  created_at: string;
  updated_at: string;
  script_count: number;
};

export type SceneScriptRelation = {
  id: number;
  scene_id: number;
  script_id: number;
  sort_order: number;
  remark: string;
  created_at: string;
  script: Script;
};

export type ScriptTask = {
  script_id: number;
  task_index: number;
  task_name: string;
  continue_on_error: boolean;
  task_content: string;
};

export type SceneTaskOutputVariable = {
  name: string;
  source_path: string;
  description: string;
};

export type SceneTaskInputBinding = {
  target_path: string;
  expression: string;
  description: string;
};

export type SceneTaskItem = {
  id: number;
  scene_id: number;
  script_id: number;
  scene_script_id?: number | null;
  task_index: number;
  task_name_snapshot: string;
  task_content_snapshot: string;
  sort_order: number;
  remark: string;
  created_at: string;
  sync_status: 'current' | 'stale' | 'missing' | string;
  sync_message: string;
  input_bindings: SceneTaskInputBinding[];
  output_variables: SceneTaskOutputVariable[];
  script: Script;
};

export type SceneCompiledScript = {
  scene_id: number;
  script_count: number;
  task_count: number;
  yaml: string;
};

export type SceneTaskSyncResult = {
  updated_count: number;
  missing_count: number;
  task_items: SceneTaskItem[];
};

export type SceneDetail = Scene & {
  scripts: SceneScriptRelation[];
  task_items: SceneTaskItem[];
};

export const sceneApi = {
  async list(): Promise<Scene[]> {
    const { data } = await http.get('/api/scenes');
    return data;
  },
  async detail(id: number): Promise<SceneDetail> {
    const { data } = await http.get(`/api/scenes/${id}`);
    return data;
  },
  async create(payload: { name: string; description: string; source_type: string }): Promise<Scene> {
    const { data } = await http.post('/api/scenes', payload);
    return data;
  },
  async copy(id: number): Promise<SceneDetail> {
    const { data } = await http.post(`/api/scenes/${id}/copy`);
    return data;
  },
  async update(id: number, payload: Partial<{ name: string; description: string; source_type: string }>): Promise<Scene> {
    const { data } = await http.put(`/api/scenes/${id}`, payload);
    return data;
  },
  async remove(id: number): Promise<void> {
    await http.delete(`/api/scenes/${id}`);
  },
  async addScript(
    sceneId: number,
    payload: { script_id: number; sort_order?: number; remark?: string },
  ): Promise<SceneScriptRelation> {
    const { data } = await http.post(`/api/scenes/${sceneId}/scripts`, payload);
    return data;
  },
  async updateScript(
    sceneId: number,
    relationId: number,
    payload: Partial<{ sort_order: number; remark: string }>,
  ): Promise<SceneScriptRelation> {
    const { data } = await http.put(`/api/scenes/${sceneId}/scripts/${relationId}`, payload);
    return data;
  },
  async removeScript(sceneId: number, relationId: number): Promise<void> {
    await http.delete(`/api/scenes/${sceneId}/scripts/${relationId}`);
  },
  async listScriptTasks(scriptId: number): Promise<ScriptTask[]> {
    const { data } = await http.get(`/api/scripts/${scriptId}/tasks`);
    return data;
  },
  async listTaskItems(sceneId: number): Promise<SceneTaskItem[]> {
    const { data } = await http.get(`/api/scenes/${sceneId}/task-items`);
    return data;
  },
  async addTaskItem(
    sceneId: number,
    payload: { script_id: number; task_index: number; remark?: string },
  ): Promise<SceneTaskItem> {
    const { data } = await http.post(`/api/scenes/${sceneId}/task-items`, payload);
    return data;
  },
  async updateTaskItem(
    sceneId: number,
    itemId: number,
    payload: Partial<{
      sort_order: number;
      remark: string;
      input_bindings: SceneTaskInputBinding[];
      output_variables: SceneTaskOutputVariable[];
    }>,
  ): Promise<SceneTaskItem> {
    const { data } = await http.put(`/api/scenes/${sceneId}/task-items/${itemId}`, payload);
    return data;
  },
  async removeTaskItem(sceneId: number, itemId: number): Promise<void> {
    await http.delete(`/api/scenes/${sceneId}/task-items/${itemId}`);
  },
  async syncTaskItem(sceneId: number, itemId: number): Promise<SceneTaskItem> {
    const { data } = await http.post(`/api/scenes/${sceneId}/task-items/${itemId}/sync`);
    return data;
  },
  async syncTaskItems(sceneId: number): Promise<SceneTaskSyncResult> {
    const { data } = await http.post(`/api/scenes/${sceneId}/task-items/sync`);
    return data;
  },
  async getCompiledScript(sceneId: number): Promise<SceneCompiledScript> {
    const { data } = await http.get(`/api/scenes/${sceneId}/compiled-script`);
    return data;
  },
};
