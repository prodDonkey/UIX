export type MigrationStatus = {
  backend: "python" | "typescript";
  phase: "bootstrap" | "dual-run" | "cutover";
  message: string;
};

export function getMigrationStatus(): MigrationStatus {
  return {
    backend: "typescript",
    phase: "dual-run",
    message: "TypeScript backend now serves scripts, scenes, and execute routes. Python backend remains the rollback baseline during migration."
  };
}
