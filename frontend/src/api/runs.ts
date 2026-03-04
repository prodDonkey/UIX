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
  current_task?: string | null;
  current_action?: string | null;
  progress_json?: string | null;
};

export type RunReport = {
  report_path: string | null;
  preview_url: string | null;
  download_url: string | null;
};

export type RunProgress = {
  run_id: number;
  status: 'queued' | 'running' | 'success' | 'failed' | 'cancelled';
  current_task: string | null;
  current_action: string | null;
  progress_json: string | null;
  updated_at: string | null;
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
  async progress(runId: number): Promise<RunProgress> {
    const { data } = await http.get(`/api/runs/${runId}/progress`);
    return data;
  },
  async cancel(runId: number): Promise<Run> {
    const { data } = await http.post(`/api/runs/${runId}/cancel`);
    return data;
  },
  async report(runId: number): Promise<RunReport> {
    const { data } = await http.get(`/api/runs/${runId}/report`);
    return data;
  },
};
