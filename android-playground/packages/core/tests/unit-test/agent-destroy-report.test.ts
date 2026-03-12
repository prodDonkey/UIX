import { Agent } from '@/agent';
import { describe, expect, it, vi } from 'vitest';

function createAgentDestroyStub() {
  const agent = Object.create(Agent.prototype) as Agent<any>;
  (agent as any).destroyed = false;
  (agent as any).dump = { executions: [] };
  (agent as any).reportFile = null;
  (agent as any).reportGenerator = {
    flush: vi.fn(async () => undefined),
    finalize: vi.fn(async () => '/tmp/report.html'),
    getReportPath: vi.fn(() => '/tmp/report.html'),
  };
  (agent as any).interface = {
    destroy: vi.fn(async () => undefined),
  };
  (agent as any).resetDump = vi.fn();
  return agent;
}

describe('Agent destroy report finalization', () => {
  it('skips finalizing an already-generated report when current dump is empty', async () => {
    const agent = createAgentDestroyStub();
    (agent as any).reportFile = '/tmp/existing-report.html';

    await agent.destroy();

    expect((agent as any).reportGenerator.flush).toHaveBeenCalledTimes(1);
    expect((agent as any).reportGenerator.finalize).not.toHaveBeenCalled();
    expect((agent as any).interface.destroy).toHaveBeenCalledTimes(1);
    expect((agent as any).resetDump).toHaveBeenCalledTimes(1);
  });

  it('still finalizes when no report file exists yet', async () => {
    const agent = createAgentDestroyStub();

    await agent.destroy();

    expect((agent as any).reportGenerator.flush).toHaveBeenCalledTimes(1);
    expect((agent as any).reportGenerator.finalize).toHaveBeenCalledTimes(1);
    expect((agent as any).reportFile).toBe('/tmp/report.html');
  });
});
