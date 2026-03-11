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

export type SceneDetail = Scene & {
  scripts: SceneScriptRelation[];
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
};
