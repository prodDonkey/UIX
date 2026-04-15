import cors from "@fastify/cors";
import Fastify from "fastify";

import { env } from "./config.js";
import { registerHealthRoutes } from "./routes/health.js";
import { registerSceneRoutes } from "./routes/scenes.js";
import { registerScriptRoutes } from "./routes/scripts.js";

export function createServer() {
  const app = Fastify({
    logger: {
      level: env.APP_ENV === "dev" ? "info" : "warn"
    }
  });

  app.register(cors, {
    origin: true,
    credentials: true
  });

  app.get("/", async () => ({
    message: `${env.APP_NAME} is running`,
    backend: "typescript"
  }));

  app.register(registerHealthRoutes);
  app.register(registerScriptRoutes);
  app.register(registerSceneRoutes);

  return app;
}
