import type { FastifyInstance } from "fastify";

import { env } from "../config.js";
import { getMigrationStatus } from "../services/migration-status.js";

export async function registerHealthRoutes(app: FastifyInstance): Promise<void> {
  app.get("/health", async () => ({
    ok: true,
    service: env.APP_NAME,
    env: env.APP_ENV,
    migration: getMigrationStatus()
  }));
}
