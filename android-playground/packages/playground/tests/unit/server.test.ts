import { ExecutionDump, GroupedActionDump } from '@midscene/core';
import { describe, expect, it, vi } from 'vitest';
import { PlaygroundServer } from '../../src/server';

function createTask(taskId: string, content: string, end: number) {
  return {
    taskId,
    type: 'Planning',
    subType: 'Plan',
    description: content,
    status: 'finished',
    param: {
      userInstruction: content,
    },
    output: {
      thought: content,
    },
    timing: {
      start: end - 1,
      end,
    },
    recorder: [],
  } as any;
}

function createExecutionDump(
  name: string,
  taskId: string,
  content: string,
  end: number,
) {
  return new ExecutionDump({
    logTime: end,
    name,
    tasks: [createTask(taskId, content, end)],
  });
}

describe('PlaygroundServer task progress dump aggregation', () => {
  it('keeps later grouped executions in task progress snapshots', () => {
    const groupedDump = new GroupedActionDump({
      sdkVersion: 'test',
      groupName: 'run-214',
      modelBriefs: [],
      executions: [
        createExecutionDump(
          'step-1',
          'task-1',
          '用户指令要求等待进入确认弹窗页面，这个目标已经达成。',
          1,
        ),
        createExecutionDump('step-2', 'task-2', '订单待用户确认', 2),
      ],
    });

    const mockAgent = {
      dumpDataString: vi.fn(() => groupedDump.serializeWithInlineScreenshots()),
      reportHTMLString: vi.fn(() => ''),
      destroy: vi.fn(),
    } as any;

    const server = new PlaygroundServer(mockAgent);
    const mergedExecution = (server as any).flattenGroupedExecutionDump(groupedDump);

    expect(mergedExecution?.tasks).toHaveLength(2);

    (server as any).mergeTaskExecutionDump('req-214', mergedExecution);

    const mergedDump = server.taskExecutionDumps['req-214'];
    expect(mergedDump?.tasks).toHaveLength(2);
    expect(
      mergedDump?.tasks?.map((task: any) => task.output?.thought || task.description),
    ).toEqual([
      '用户指令要求等待进入确认弹窗页面，这个目标已经达成。',
      '订单待用户确认',
    ]);
  });
});
