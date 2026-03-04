export interface RunnerConfig {
  host: string;
  port: number;
}

const defaultPort = 8100;

function parsePort(rawPort: string | undefined): number {
  if (!rawPort) return defaultPort;
  const parsed = Number(rawPort);
  if (!Number.isInteger(parsed) || parsed <= 0 || parsed > 65535) {
    return defaultPort;
  }
  return parsed;
}

export function loadConfig(env: NodeJS.ProcessEnv = process.env): RunnerConfig {
  return {
    host: env.RUNNER_HOST || "127.0.0.1",
    port: parsePort(env.RUNNER_PORT)
  };
}
