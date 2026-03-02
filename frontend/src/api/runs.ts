import { http } from './client';

export type Run = {
  id: number;
  script_id: number;
  status: 'queued' | 'running' | 'success' | 'failed' | 'cancelled';
  started_at: string | null;
  ended_at: string | null;
  duration_ms: number | null;
  log_path: string | null;
  report_path: string | null;
  summary_path: string | null;
  error_message: string | null;
};

export const runApi = {
  async create(scriptId: number): Promise<Run> {
    const { data } = await http.post('/api/runs', { script_id: scriptId });
    return data;
  },
  async list(scriptId?: number): Promise<Run[]> {
    const { data } = await http.get('/api/runs', {
      params: scriptId ? { script_id: scriptId } : undefined,
    });
    return data;
  },
  async detail(runId: number): Promise<Run> {
    const { data } = await http.get(`/api/runs/${runId}`);
    return data;
  },
  async logs(runId: number): Promise<{ content: string }> {
    const { data } = await http.get(`/api/runs/${runId}/logs`);
    return data;
  },
  async cancel(runId: number): Promise<Run> {
    const { data } = await http.post(`/api/runs/${runId}/cancel`);
    return data;
  },
  async report(runId: number): Promise<{ report_path: string | null }> {
    const { data } = await http.get(`/api/runs/${runId}/report`);
    return data;
  },
};

