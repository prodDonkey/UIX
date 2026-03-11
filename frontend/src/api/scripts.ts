import { http } from './client';

const GENERATE_TIMEOUT_MS = 90_000;

export type Script = {
  id: number;
  name: string;
  content: string;
  source_type: string;
  created_at: string;
  updated_at: string;
  scene_count?: number;
  scenes?: Array<{ id: number; name: string }>;
};

export type ValidateResult = {
  valid: boolean;
  line?: number;
  column?: number;
  message?: string;
};

export type GenerateScriptPayload = {
  prompt: string;
  device_id?: string;
  language?: 'zh' | 'en';
  model?: string;
};

export type GenerateScriptResult = {
  yaml: string;
  warnings: string[];
};

export const scriptApi = {
  async list(): Promise<Script[]> {
    const { data } = await http.get('/api/scripts');
    return data;
  },
  async detail(id: number): Promise<Script> {
    const { data } = await http.get(`/api/scripts/${id}`);
    return data;
  },
  async create(payload: { name: string; content: string; source_type: string }): Promise<Script> {
    const { data } = await http.post('/api/scripts', payload);
    return data;
  },
  async update(id: number, payload: Partial<{ name: string; content: string; source_type: string }>): Promise<Script> {
    const { data } = await http.put(`/api/scripts/${id}`, payload);
    return data;
  },
  async remove(id: number): Promise<void> {
    await http.delete(`/api/scripts/${id}`);
  },
  async copy(id: number): Promise<Script> {
    const { data } = await http.post(`/api/scripts/${id}/copy`);
    return data;
  },
  async validate(id: number, content: string): Promise<ValidateResult> {
    const { data } = await http.post(`/api/scripts/${id}/validate`, { content });
    return data;
  },
  async generate(payload: GenerateScriptPayload): Promise<GenerateScriptResult> {
    const { data } = await http.post('/api/scripts/generate', payload, {
      timeout: GENERATE_TIMEOUT_MS,
    });
    return data;
  },
};
