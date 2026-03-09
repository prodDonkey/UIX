import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import http from 'node:http';
import type { Server } from 'node:http';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import type { ExecutionDump, IExecutionDump } from '@midscene/core';
import { GroupedActionDump } from '@midscene/core';
import type { Agent as PageAgent } from '@midscene/core/agent';
import { getTmpDir } from '@midscene/core/utils';
import { PLAYGROUND_SERVER_PORT } from '@midscene/shared/constants';
import {
  globalModelConfigManager,
  overrideAIConfig,
} from '@midscene/shared/env';
import { uuid } from '@midscene/shared/utils';
import express, { type Request, type Response } from 'express';
import { executeAction, formatErrorMessage } from './common';

import 'dotenv/config';

const defaultPort = PLAYGROUND_SERVER_PORT;

// Static path for playground files
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const STATIC_PATH = join(__dirname, '..', '..', 'static');

const errorHandler = (
  err: unknown,
  req: Request,
  res: Response,
  next: express.NextFunction,
) => {
  console.error(err);
  const errorMessage =
    err instanceof Error ? err.message : 'Internal server error';
  res.status(500).json({
    error: errorMessage,
  });
};

type AsyncTaskStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled';

interface AsyncTaskResult {
  requestId: string;
  type: string;
  status: AsyncTaskStatus;
  result: unknown;
  dump: ExecutionDump | null;
  error: string | null;
  reportHTML: string | null;
  reportPath: string | null;
  createdAt: number;
  startedAt: number | null;
  finishedAt: number | null;
}

function normalizeReportHTML(html: string | null | undefined): string | null {
  if (!html || typeof html !== 'string') {
    return null;
  }
  return html.includes('REPLACE_ME_WITH_REPORT_HTML') ? null : html;
}

function getAgentReportPath(agent: PageAgent | null | undefined): string | null {
  const reportFile =
    agent && typeof agent === 'object' && 'reportFile' in agent
      ? (agent as { reportFile?: unknown }).reportFile
      : null;
  return typeof reportFile === 'string' && reportFile.trim() ? reportFile.trim() : null;
}

class PlaygroundServer {
  private _app: express.Application;
  tmpDir: string;
  server?: Server;
  port?: number | null;
  agent: PageAgent;
  staticPath: string;
  reportDir?: string; // Optional report directory for static file serving
  taskExecutionDumps: Record<string, IExecutionDump | null>; // Store execution dump snapshots
  taskResults: Record<string, AsyncTaskResult>;
  id: string; // Unique identifier for this server instance

  private _initialized = false;

  // Native MJPEG stream probe: null = not tested, true/false = result
  private _nativeMjpegAvailable: boolean | null = null;

  // Factory function for recreating agent
  private agentFactory?: (() => PageAgent | Promise<PageAgent>) | null;

  // Track current running task
  private currentTaskId: string | null = null;

  // Flag to pause MJPEG polling during agent recreation
  private _agentReady = true;

  constructor(
    agent: PageAgent | (() => PageAgent) | (() => Promise<PageAgent>),
    staticPath = STATIC_PATH,
    reportDir?: string, // Optional report directory for static file serving
    id?: string, // Optional override ID
  ) {
    this._app = express();
    this.tmpDir = getTmpDir()!;
    this.staticPath = staticPath;
    this.reportDir = reportDir;
    this.taskExecutionDumps = {}; // Initialize as empty object
    this.taskResults = {};
    // Use provided ID, or generate random UUID for each startup
    this.id = id || uuid();

    // Support both instance and factory function modes
    if (typeof agent === 'function') {
      this.agentFactory = agent;
      this.agent = null as any; // Will be initialized in launch()
    } else {
      this.agent = agent;
      this.agentFactory = null;
    }
  }

  /**
   * Get the Express app instance for custom configuration
   *
   * IMPORTANT: Add middleware (like CORS) BEFORE calling launch()
   * The routes are initialized when launch() is called, so middleware
   * added after launch() will not affect the API routes.
   *
   * @example
   * ```typescript
   * import cors from 'cors';
   *
   * const server = new PlaygroundServer(agent);
   *
   * // Add CORS middleware before launch
   * server.app.use(cors({
   *   origin: true,
   *   credentials: true,
   *   methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']
   * }));
   *
   * await server.launch();
   * ```
   */
  get app(): express.Application {
    return this._app;
  }

  /**
   * Initialize Express app with all routes and middleware
   * Called automatically by launch() if not already initialized
   */
  private initializeApp(): void {
    if (this._initialized) return;

    // Built-in middleware to parse JSON bodies
    this._app.use(express.json({ limit: '50mb' }));

    // Context update middleware (after JSON parsing)
    this._app.use(
      (req: Request, _res: Response, next: express.NextFunction) => {
        const { context } = req.body || {};
        if (
          context &&
          'updateContext' in this.agent.interface &&
          typeof this.agent.interface.updateContext === 'function'
        ) {
          this.agent.interface.updateContext(context);
          console.log('Context updated by PlaygroundServer middleware');
        }
        next();
      },
    );

    // NOTE: CORS middleware should be added externally via server.app.use()
    // before calling server.launch() if needed

    // API routes
    this.setupRoutes();

    // Static file serving (if staticPath is provided)
    this.setupStaticRoutes();

    // Error handler middleware (must be last)
    this._app.use(errorHandler);

    this._initialized = true;
  }

  filePathForUuid(uuid: string) {
    // Validate uuid to prevent path traversal attacks
    // Only allow alphanumeric characters and hyphens
    if (!/^[a-zA-Z0-9-]+$/.test(uuid)) {
      throw new Error('Invalid uuid format');
    }
    const filePath = join(this.tmpDir, `${uuid}.json`);
    // Double-check that resolved path is within tmpDir
    const resolvedPath = resolve(filePath);
    const resolvedTmpDir = resolve(this.tmpDir);
    if (!resolvedPath.startsWith(resolvedTmpDir)) {
      throw new Error('Invalid path');
    }
    return filePath;
  }

  saveContextFile(uuid: string, context: string) {
    const tmpFile = this.filePathForUuid(uuid);
    console.log(`save context file: ${tmpFile}`);
    writeFileSync(tmpFile, context);
    return tmpFile;
  }

  /**
   * Recreate agent instance (for cancellation)
   */
  private async recreateAgent(): Promise<void> {
    if (!this.agentFactory) {
      throw new Error(
        'Cannot recreate agent: factory function not provided. Attempting to destroy existing agent only.',
      );
    }

    this._agentReady = false;
    console.log('Recreating agent to cancel current task...');

    // Destroy old agent instance
    try {
      if (this.agent && typeof this.agent.destroy === 'function') {
        await this.agent.destroy();
      }
    } catch (error) {
      console.warn('Failed to destroy old agent:', error);
    }

    // Create new agent instance
    try {
      this.agent = await this.agentFactory();
      this._agentReady = true;
      console.log('Agent recreated successfully');
    } catch (error) {
      this._agentReady = true;
      console.error('Failed to recreate agent:', error);
      throw error;
    }
  }

  private createAsyncTaskRecord(
    requestId: string,
    type: string,
  ): AsyncTaskResult {
    return {
      requestId,
      type,
      status: 'pending',
      result: null,
      dump: null,
      error: null,
      reportHTML: null,
      reportPath: null,
      createdAt: Date.now(),
      startedAt: null,
      finishedAt: null,
    };
  }

  private updateTaskExecutionDump(
    requestId: string,
    fallbackDump?: ExecutionDump | IExecutionDump,
  ): void {
    try {
      const dumpString = this.agent.dumpDataString({
        inlineScreenshots: true,
      });
      if (dumpString) {
        const groupedDump = GroupedActionDump.fromSerializedString(dumpString);
        const bestExecution =
          groupedDump.executions?.reduce((acc, current) => {
            const accCount = acc?.tasks?.length || 0;
            const currentCount = current?.tasks?.length || 0;
            return currentCount >= accCount ? current : acc;
          }, groupedDump.executions?.[0]) || null;
        this.mergeTaskExecutionDump(requestId, bestExecution || undefined);
        return;
      }
    } catch (error) {
      // Fallback to callback payload when full dump snapshot is unavailable.
    }

    this.mergeTaskExecutionDump(requestId, fallbackDump);
  }

  private taskKey(task: any): string {
    const timingStart = task?.timing?.start || '';
    const timingEnd = task?.timing?.end || '';
    const type = task?.type || '';
    const desc = task?.description || '';
    const param =
      task?.param !== undefined
        ? task.param
        : task?.params !== undefined
          ? task.params
          : task?.locate !== undefined
            ? task.locate
            : null;
    return `${timingStart}|${timingEnd}|${type}|${desc}|${JSON.stringify(param)}`;
  }

  private mergeTaskExecutionDump(
    requestId: string,
    incomingDump?: ExecutionDump | IExecutionDump,
  ): void {
    if (!incomingDump) return;

    const existingDump = this.taskExecutionDumps[requestId];
    if (!existingDump?.tasks?.length) {
      this.taskExecutionDumps[requestId] = {
        ...(incomingDump as any),
        tasks: Array.isArray((incomingDump as any).tasks)
          ? [...(incomingDump as any).tasks]
          : [],
      };
      return;
    }

    const existingTasks = Array.isArray(existingDump.tasks)
      ? existingDump.tasks
      : [];
    const incomingTasks = Array.isArray(incomingDump.tasks)
      ? incomingDump.tasks
      : [];
    const mergedTasks = [...existingTasks];
    const taskKeySet = new Set(existingTasks.map((task) => this.taskKey(task)));

    for (const task of incomingTasks) {
      const key = this.taskKey(task);
      if (!taskKeySet.has(key)) {
        mergedTasks.push(task);
        taskKeySet.add(key);
      }
    }

    this.taskExecutionDumps[requestId] = {
      ...(incomingDump as any),
      tasks: mergedTasks,
    };
  }

  private collectTaskArtifacts(task: AsyncTaskResult, requestId: string): void {
    try {
      const dumpString = this.agent.dumpDataString({
        inlineScreenshots: true,
      });
      if (dumpString) {
        const groupedDump = GroupedActionDump.fromSerializedString(dumpString);
        task.dump =
          groupedDump.executions?.reduce((acc, current) => {
            const accCount = acc?.tasks?.length || 0;
            const currentCount = current?.tasks?.length || 0;
            return currentCount >= accCount ? current : acc;
          }, groupedDump.executions?.[0]) || null;
        this.mergeTaskExecutionDump(requestId, task.dump || undefined);
      task.dump =
          (this.taskExecutionDumps[requestId] as ExecutionDump | null) ||
          task.dump;
      }
      task.reportHTML = normalizeReportHTML(
        this.agent.reportHTMLString({ inlineScreenshots: true }) || null,
      );
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : 'Unknown error';
      console.warn(
        `[run-yaml] Failed to collect dump/report for ${requestId}: ${errorMessage}`,
      );
    }
    task.reportPath = getAgentReportPath(this.agent);
  }

  private async runYamlTaskInBackground(
    requestId: string,
    yamlScript: string,
    options: {
      deepLocate?: boolean;
      deepThink?: boolean;
      screenshotIncluded?: boolean;
      domIncluded?: boolean;
      deviceOptions?: unknown;
    },
  ): Promise<void> {
    const task = this.taskResults[requestId];
    if (!task) return;

    this.currentTaskId = requestId;
    this.taskExecutionDumps[requestId] = null;
    task.status = 'running';
    task.startedAt = Date.now();

    try {
      // Always recreate agent before execution to ensure latest config is applied
      if (this.agentFactory) {
        this._agentReady = false;
        console.log(`[run-yaml] Destroying old agent: ${requestId}`);
        try {
          if (this.agent && typeof this.agent.destroy === 'function') {
            await this.agent.destroy();
          }
        } catch (error) {
          console.warn(
            `[run-yaml] Failed to destroy old agent: ${requestId}`,
            error,
          );
        }

        console.log(`[run-yaml] Creating new agent: ${requestId}`);
        this.agent = await this.agentFactory();
        this._agentReady = true;
      }

      // Update device options if provided
      if (
        options.deviceOptions &&
        this.agent.interface &&
        'options' in this.agent.interface
      ) {
        this.agent.interface.options = {
          ...(this.agent.interface.options || {}),
          ...(options.deviceOptions as Record<string, unknown>),
        };
      }

      this.agent.onDumpUpdate = (_dump: string, executionDump?: ExecutionDump) => {
        this.updateTaskExecutionDump(requestId, executionDump);
      };

      const actionSpace = this.agent.interface.actionSpace();
      task.result = await executeAction(
        this.agent,
        'runYaml',
        actionSpace,
        {
          type: 'runYaml',
          prompt: yamlScript,
        },
        {
          requestId,
          deepLocate: options.deepLocate,
          deepThink: options.deepThink,
          screenshotIncluded: options.screenshotIncluded,
          domIncluded: options.domIncluded,
          deviceOptions: options.deviceOptions as any,
        },
      );

      this.collectTaskArtifacts(task, requestId);

      try {
        this.agent.writeOutActionDumps();
        this.agent.resetDump();
      } catch (error) {
        console.warn(`[run-yaml] Failed to write/reset dump: ${requestId}`, error);
      }

      if (this.taskResults[requestId]?.status === 'cancelled') {
        console.log(`[run-yaml] Task cancelled before completion: ${requestId}`);
        return;
      }

      task.status = 'completed';
      task.finishedAt = Date.now();
      console.log(`[run-yaml] Task completed: ${requestId}`);
    } catch (error: unknown) {
      if (this.taskResults[requestId]?.status === 'cancelled') {
        console.log(`[run-yaml] Task cancelled: ${requestId}`);
        return;
      }
      this.collectTaskArtifacts(task, requestId);
      task.error = formatErrorMessage(error);
      task.status = 'failed';
      task.finishedAt = Date.now();
      console.error(`[run-yaml] Task failed: ${requestId}, ${task.error}`);
    } finally {
      if (this.currentTaskId === requestId) {
        this.currentTaskId = null;
      }
    }
  }

  /**
   * Setup all API routes
   */
  private setupRoutes(): void {
    this._app.get('/status', async (req: Request, res: Response) => {
      res.send({
        status: 'ok',
        id: this.id,
      });
    });

    this._app.get('/context/:uuid', async (req: Request, res: Response) => {
      const { uuid } = req.params;
      let contextFile: string;
      try {
        contextFile = this.filePathForUuid(uuid);
      } catch {
        return res.status(400).json({
          error: 'Invalid uuid format',
        });
      }

      if (!existsSync(contextFile)) {
        return res.status(404).json({
          error: 'Context not found',
        });
      }

      const context = readFileSync(contextFile, 'utf8');
      res.json({
        context,
      });
    });

    this._app.get(
      '/task-progress/:requestId',
      async (req: Request, res: Response) => {
        const { requestId } = req.params;
        const executionDump = this.taskExecutionDumps[requestId] || null;

        res.json({
          executionDump,
        });
      },
    );

    this._app.get('/task-result/:requestId', async (req: Request, res: Response) => {
      const { requestId } = req.params;
      const taskResult = this.taskResults[requestId];

      if (!taskResult) {
        return res.status(404).json({
          error: 'Task result not found',
          requestId,
          status: 'not_found',
        });
      }

      return res.json(taskResult);
    });

    this._app.post('/run-yaml', async (req: Request, res: Response) => {
      const {
        yaml,
        prompt,
        requestId: rawRequestId,
        deepLocate,
        deepThink,
        screenshotIncluded,
        domIncluded,
        deviceOptions,
      } = req.body || {};

      const yamlScript = typeof yaml === 'string' ? yaml : prompt;

      if (!yamlScript || typeof yamlScript !== 'string') {
        return res.status(400).json({
          error: 'yaml is required',
        });
      }

      if (this.currentTaskId) {
        return res.status(409).json({
          error: 'Another task is already running',
          currentTaskId: this.currentTaskId,
        });
      }

      const requestId =
        typeof rawRequestId === 'string' && rawRequestId.trim()
          ? rawRequestId.trim()
          : uuid();

      if (this.taskResults[requestId]?.status === 'running') {
        return res.status(409).json({
          error: 'Task already running',
          requestId,
        });
      }

      this.taskResults[requestId] = this.createAsyncTaskRecord(
        requestId,
        'runYaml',
      );

      res.json({
        requestId,
        status: 'accepted',
      });

      void this.runYamlTaskInBackground(requestId, yamlScript, {
        deepLocate,
        deepThink,
        screenshotIncluded,
        domIncluded,
        deviceOptions,
      });
    });

    this._app.post('/action-space', async (req: Request, res: Response) => {
      try {
        let actionSpace = [];

        actionSpace = this.agent.interface.actionSpace();

        // Process actionSpace to make paramSchema serializable with shape info
        const processedActionSpace = actionSpace.map((action: unknown) => {
          if (action && typeof action === 'object' && 'paramSchema' in action) {
            const typedAction = action as {
              paramSchema?: { shape?: object; [key: string]: unknown };
              [key: string]: unknown;
            };
            if (
              typedAction.paramSchema &&
              typeof typedAction.paramSchema === 'object'
            ) {
              // Extract shape information from Zod schema
              let processedSchema = null;

              try {
                // Extract shape from runtime Zod object
                if (
                  typedAction.paramSchema.shape &&
                  typeof typedAction.paramSchema.shape === 'object'
                ) {
                  processedSchema = {
                    type: 'ZodObject',
                    shape: typedAction.paramSchema.shape,
                  };
                }
              } catch (e) {
                const actionName =
                  'name' in typedAction && typeof typedAction.name === 'string'
                    ? typedAction.name
                    : 'unknown';
                console.warn(
                  'Failed to process paramSchema for action:',
                  actionName,
                  e,
                );
              }

              return {
                ...typedAction,
                paramSchema: processedSchema,
              };
            }
          }
          return action;
        });

        res.json(processedActionSpace);
      } catch (error: unknown) {
        const errorMessage =
          error instanceof Error ? error.message : 'Unknown error';
        console.error('Failed to get action space:', error);
        res.status(500).json({
          error: errorMessage,
        });
      }
    });

    // -------------------------
    // actions from report file
    this._app.post(
      '/playground-with-context',
      async (req: Request, res: Response) => {
        const context = req.body.context;

        if (!context) {
          return res.status(400).json({
            error: 'context is required',
          });
        }

        const requestId = uuid();
        this.saveContextFile(requestId, context);
        return res.json({
          location: `/playground/${requestId}`,
          uuid: requestId,
        });
      },
    );

    this._app.post('/execute', async (req: Request, res: Response) => {
      const {
        type,
        prompt,
        params,
        requestId,
        deepLocate,
        deepThink,
        screenshotIncluded,
        domIncluded,
        deviceOptions,
      } = req.body;

      if (!type) {
        return res.status(400).json({
          error: 'type is required',
        });
      }

      // Always recreate agent before execution to ensure latest config is applied
      if (this.agentFactory) {
        this._agentReady = false;
        console.log('Destroying old agent before execution...');
        try {
          if (this.agent && typeof this.agent.destroy === 'function') {
            await this.agent.destroy();
          }
        } catch (error) {
          console.warn('Failed to destroy old agent:', error);
        }

        console.log('Creating new agent with latest config...');
        try {
          this.agent = await this.agentFactory();
          this._agentReady = true;
          console.log('Agent created successfully');
        } catch (error) {
          this._agentReady = true;
          console.error('Failed to create agent:', error);
          return res.status(500).json({
            error: `Failed to create agent: ${error instanceof Error ? error.message : 'Unknown error'}`,
          });
        }
      }

      // Update device options if provided
      if (
        deviceOptions &&
        this.agent.interface &&
        'options' in this.agent.interface
      ) {
        this.agent.interface.options = {
          ...(this.agent.interface.options || {}),
          ...deviceOptions,
        };
      }

      // Check if another task is running
      if (this.currentTaskId) {
        return res.status(409).json({
          error: 'Another task is already running',
          currentTaskId: this.currentTaskId,
        });
      }

      // Lock this task
      if (requestId) {
        this.currentTaskId = requestId;
        this.taskExecutionDumps[requestId] = null;

        // Keep full history snapshot so late subscribers can see previous steps.
        this.agent.onDumpUpdate = (
          _dump: string,
          executionDump?: ExecutionDump,
        ) => {
          this.updateTaskExecutionDump(requestId, executionDump);
        };
      }

      const response: {
        result: unknown;
        dump: ExecutionDump | null;
        error: string | null;
        reportHTML: string | null;
        reportPath: string | null;
        requestId?: string;
      } = {
        result: null,
        dump: null,
        error: null,
        reportHTML: null,
        reportPath: null,
        requestId,
      };

      const startTime = Date.now();
      try {
        // Get action space to check for dynamic actions
        const actionSpace = this.agent.interface.actionSpace();

        // Prepare value object for executeAction
        const value = {
          type,
          prompt,
          params,
        };

        response.result = await executeAction(
          this.agent,
          type,
          actionSpace,
          value,
          {
            deepLocate,
            deepThink,
            screenshotIncluded,
            domIncluded,
            deviceOptions,
          },
        );
      } catch (error: unknown) {
        response.error = formatErrorMessage(error);
      }

      try {
        const dumpString = this.agent.dumpDataString({
          inlineScreenshots: true,
        });
        if (dumpString) {
          const groupedDump =
            GroupedActionDump.fromSerializedString(dumpString);
          response.dump =
            groupedDump.executions?.reduce((acc, current) => {
              const accCount = acc?.tasks?.length || 0;
              const currentCount = current?.tasks?.length || 0;
              return currentCount >= accCount ? current : acc;
            }, groupedDump.executions?.[0]) || null;
        } else {
          response.dump = null;
        }
        response.reportHTML = normalizeReportHTML(
          this.agent.reportHTMLString({ inlineScreenshots: true }) || null,
        );

        this.agent.writeOutActionDumps();
        response.reportPath = getAgentReportPath(this.agent);
        this.agent.resetDump();
      } catch (error: unknown) {
        const errorMessage =
          error instanceof Error ? error.message : 'Unknown error';
        console.error(
          `write out dump failed: requestId: ${requestId}, ${errorMessage}`,
        );
      }

      res.send(response);
      const timeCost = Date.now() - startTime;

      if (response.error) {
        console.error(
          `handle request failed after ${timeCost}ms: requestId: ${requestId}, ${response.error}`,
        );
      } else {
        console.log(
          `handle request done after ${timeCost}ms: requestId: ${requestId}`,
        );
      }

      // Clean up task execution dumps and unlock after execution completes
      if (requestId) {
        delete this.taskExecutionDumps[requestId];
        // Release the lock
        if (this.currentTaskId === requestId) {
          this.currentTaskId = null;
        }
      }
    });

    this._app.post(
      '/cancel/:requestId',
      async (req: Request, res: Response) => {
        const { requestId } = req.params;

        if (!requestId) {
          return res.status(400).json({
            error: 'requestId is required',
          });
        }

        try {
          // Check if this is the current running task
          if (this.currentTaskId !== requestId) {
            return res.json({
              status: 'not_found',
              message: 'Task not found or already completed',
            });
          }

          console.log(`Cancelling task: ${requestId}`);

          // Get current execution data before cancelling (dump and reportHTML)
          let dump: any = null;
          let reportHTML: string | null = null;
          let reportPath: string | null = null;

          try {
            const dumpString = this.agent.dumpDataString?.({
              inlineScreenshots: true,
            });
            if (dumpString) {
              const groupedDump =
                GroupedActionDump.fromSerializedString(dumpString);
              // Extract first execution from grouped dump
              dump = groupedDump.executions?.[0] || null;
            }

            reportHTML = normalizeReportHTML(
              this.agent.reportHTMLString?.({ inlineScreenshots: true }) ||
                null,
            );
            reportPath = getAgentReportPath(this.agent);
          } catch (error: unknown) {
            console.warn('Failed to get execution data before cancel:', error);
          }

          // Destroy agent to cancel the current task
          // No need to recreate here — /execute always creates a fresh agent before each run
          try {
            if (this.agent && typeof this.agent.destroy === 'function') {
              await this.agent.destroy();
            }
          } catch (error) {
            console.warn('Failed to destroy agent during cancel:', error);
          }

          // Persist cancellation result so later task-result queries can still read it.
          const task = this.taskResults[requestId];
          if (task) {
            task.status = 'cancelled';
            task.finishedAt = Date.now();
            task.dump = dump;
            task.reportHTML = reportHTML;
            task.reportPath = reportPath;
            task.error = null;
          }

          // Clean up
          delete this.taskExecutionDumps[requestId];
          this.currentTaskId = null;

          res.json({
            status: 'cancelled',
            message: 'Task cancelled successfully',
            dump,
            reportHTML,
            reportPath,
          });
        } catch (error: unknown) {
          const errorMessage =
            error instanceof Error ? error.message : 'Unknown error';
          console.error(`Failed to cancel: ${errorMessage}`);
          res.status(500).json({
            error: `Failed to cancel: ${errorMessage}`,
          });
        }
      },
    );

    // Screenshot API for real-time screenshot polling
    this._app.get('/screenshot', async (_req: Request, res: Response) => {
      try {
        // Check if page has screenshotBase64 method
        if (typeof this.agent.interface.screenshotBase64 !== 'function') {
          return res.status(500).json({
            error: 'Screenshot method not available on current interface',
          });
        }

        const base64Screenshot = await this.agent.interface.screenshotBase64();

        res.json({
          screenshot: base64Screenshot,
          timestamp: Date.now(),
        });
      } catch (error: unknown) {
        const errorMessage =
          error instanceof Error ? error.message : 'Unknown error';
        console.error(`Failed to take screenshot: ${errorMessage}`);
        res.status(500).json({
          error: `Failed to take screenshot: ${errorMessage}`,
        });
      }
    });

    // MJPEG streaming endpoint for real-time screen preview
    // Proxies native MJPEG stream (e.g. WDA MJPEG server) when available,
    // falls back to polling screenshotBase64() otherwise.
    this._app.get('/mjpeg', async (req: Request, res: Response) => {
      const nativeUrl = this.agent?.interface?.mjpegStreamUrl;

      if (nativeUrl && this._nativeMjpegAvailable !== false) {
        const proxyOk = await this.probeAndProxyNativeMjpeg(
          nativeUrl,
          req,
          res,
        );
        if (proxyOk) return;
      }

      if (typeof this.agent?.interface?.screenshotBase64 !== 'function') {
        return res.status(500).json({
          error: 'Screenshot method not available on current interface',
        });
      }

      await this.startPollingMjpegStream(req, res);
    });

    // Interface info API for getting interface type and description
    this._app.get('/interface-info', async (_req: Request, res: Response) => {
      try {
        const type = this.agent.interface.interfaceType || 'Unknown';
        const description = this.agent.interface.describe?.() || undefined;

        res.json({
          type,
          description,
        });
      } catch (error: unknown) {
        const errorMessage =
          error instanceof Error ? error.message : 'Unknown error';
        console.error(`Failed to get interface info: ${errorMessage}`);
        res.status(500).json({
          error: `Failed to get interface info: ${errorMessage}`,
        });
      }
    });

    this.app.post('/config', async (req: Request, res: Response) => {
      const { aiConfig } = req.body;

      if (!aiConfig || typeof aiConfig !== 'object') {
        return res.status(400).json({
          error: 'aiConfig is required and must be an object',
        });
      }

      if (Object.keys(aiConfig).length === 0) {
        return res.json({
          status: 'ok',
          message: 'AI config not changed due to empty object',
        });
      }

      try {
        overrideAIConfig(aiConfig);
      } catch (error: unknown) {
        const errorMessage =
          error instanceof Error ? error.message : 'Unknown error';
        console.error(`Failed to update AI config: ${errorMessage}`);
        return res.status(500).json({
          error: `Failed to update AI config: ${errorMessage}`,
        });
      }

      // Validate the config immediately so the frontend gets early feedback
      try {
        globalModelConfigManager.getModelConfig('default');
      } catch (error: unknown) {
        const errorMessage =
          error instanceof Error ? error.message : 'Unknown error';
        console.error(`AI config validation failed: ${errorMessage}`);
        return res.status(400).json({
          error: errorMessage,
        });
      }

      // Note: Agent will be recreated on next execution to apply new config
      return res.json({
        status: 'ok',
        message:
          'AI config updated. Agent will be recreated on next execution.',
      });
    });
  }

  /**
   * Probe and proxy a native MJPEG stream (e.g. WDA MJPEG server).
   * Result is cached so we only probe once per server lifetime.
   */
  private probeAndProxyNativeMjpeg(
    nativeUrl: string,
    req: Request,
    res: Response,
  ): Promise<boolean> {
    return new Promise<boolean>((resolve) => {
      console.log(`MJPEG: trying native stream from ${nativeUrl}`);
      const proxyReq = http.get(nativeUrl, (proxyRes) => {
        this._nativeMjpegAvailable = true;
        console.log('MJPEG: streaming via native WDA MJPEG server');
        const contentType = proxyRes.headers['content-type'];
        if (contentType) {
          res.setHeader('Content-Type', contentType);
        }
        res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate');
        res.setHeader('Connection', 'keep-alive');
        proxyRes.pipe(res);
        req.on('close', () => proxyReq.destroy());
        resolve(true);
      });
      proxyReq.on('error', (err) => {
        this._nativeMjpegAvailable = false;
        console.warn(
          `MJPEG: native stream unavailable (${err.message}), using polling mode`,
        );
        resolve(false);
      });
    });
  }

  /**
   * Stream screenshots as MJPEG by polling screenshotBase64().
   */
  private async startPollingMjpegStream(
    req: Request,
    res: Response,
  ): Promise<void> {
    const defaultMjpegFps = 10;
    const maxMjpegFps = 30;
    const maxErrorBackoffMs = 3000;
    const errorLogThreshold = 3;

    const parsedFps = Number(req.query.fps);
    const fps = Math.min(
      Math.max(Number.isNaN(parsedFps) ? defaultMjpegFps : parsedFps, 1),
      maxMjpegFps,
    );
    const interval = Math.round(1000 / fps);
    const boundary = 'mjpeg-boundary';
    console.log(`MJPEG: streaming via polling mode (${fps}fps)`);

    res.setHeader(
      'Content-Type',
      `multipart/x-mixed-replace; boundary=${boundary}`,
    );
    res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate');
    res.setHeader('Connection', 'keep-alive');

    let stopped = false;
    let consecutiveErrors = 0;
    req.on('close', () => {
      stopped = true;
    });

    while (!stopped) {
      // Skip frame while agent is being recreated
      if (!this._agentReady) {
        await new Promise((r) => setTimeout(r, 200));
        continue;
      }

      const frameStart = Date.now();
      try {
        const base64 = await this.agent.interface.screenshotBase64();
        if (stopped) break;
        consecutiveErrors = 0;

        const raw = base64.replace(/^data:image\/\w+;base64,/, '');
        const buf = Buffer.from(raw, 'base64');

        res.write(`--${boundary}\r\n`);
        res.write('Content-Type: image/jpeg\r\n');
        res.write(`Content-Length: ${buf.length}\r\n\r\n`);
        res.write(buf);
        res.write('\r\n');
      } catch (err) {
        if (stopped) break;
        consecutiveErrors++;
        if (consecutiveErrors <= errorLogThreshold) {
          console.error('MJPEG frame error:', err);
        } else if (consecutiveErrors === errorLogThreshold + 1) {
          console.error(
            'MJPEG: suppressing further errors, retrying silently...',
          );
        }
        const backoff = Math.min(1000 * consecutiveErrors, maxErrorBackoffMs);
        await new Promise((r) => setTimeout(r, backoff));
        continue;
      }

      const elapsed = Date.now() - frameStart;
      const remaining = interval - elapsed;
      if (remaining > 0) {
        await new Promise((r) => setTimeout(r, remaining));
      }
    }
  }

  /**
   * Setup static file serving routes
   */
  private setupStaticRoutes(): void {
    // Handle index.html with port injection
    this._app.get('/', (_req: Request, res: Response) => {
      this.serveHtmlWithPorts(res);
    });

    this._app.get('/index.html', (_req: Request, res: Response) => {
      this.serveHtmlWithPorts(res);
    });

    // Use express.static middleware for secure static file serving
    this._app.use(express.static(this.staticPath));

    // Serve report directory files at /report路径
    if (this.reportDir) {
      this._app.use('/report', express.static(this.reportDir));
    }

    // Fallback to index.html for SPA routing
    this._app.get('*', (_req: Request, res: Response) => {
      this.serveHtmlWithPorts(res);
    });
  }

  /**
   * Serve HTML with injected port configuration
   */
  private serveHtmlWithPorts(res: Response): void {
    try {
      const htmlPath = join(this.staticPath, 'index.html');
      let html = readFileSync(htmlPath, 'utf8');

      // Get scrcpy server port from global
      const scrcpyPort = (global as any).scrcpyServerPort || this.port! + 1;

      // Inject scrcpy port configuration script into HTML head
      const configScript = `
        <script>
          window.SCRCPY_PORT = ${scrcpyPort};
        </script>
      `;

      // Insert the script before closing </head> tag
      html = html.replace('</head>', `${configScript}</head>`);

      res.setHeader('Content-Type', 'text/html');
      res.send(html);
    } catch (error) {
      console.error('Error serving HTML with ports:', error);
      res.status(500).send('Internal Server Error');
    }
  }

  /**
   * Launch the server on specified port
   */
  async launch(port?: number): Promise<PlaygroundServer> {
    // If using factory mode, initialize agent
    if (this.agentFactory) {
      console.log('Initializing agent from factory function...');
      this.agent = await this.agentFactory();
      console.log('Agent initialized successfully');
    }

    // Initialize routes now, after any middleware has been added
    this.initializeApp();

    this.port = port || defaultPort;

    return new Promise((resolve) => {
      const serverPort = this.port;
      this.server = this._app.listen(serverPort, () => {
        resolve(this);
      });
    });
  }

  /**
   * Close the server and clean up resources
   */
  async close(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.server) {
        // Clean up the single agent
        try {
          this.agent.destroy();
        } catch (error) {
          console.warn('Failed to destroy agent:', error);
        }
        this.taskExecutionDumps = {};

        // Close the server
        this.server.close((error) => {
          if (error) {
            reject(error);
          } else {
            this.server = undefined;
            resolve();
          }
        });
      } else {
        resolve();
      }
    });
  }
}

export default PlaygroundServer;
export { PlaygroundServer };
