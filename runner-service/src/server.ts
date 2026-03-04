import Fastify from "fastify";
import { loadConfig } from "./config.js";

const config = loadConfig();

/**
 * Runner HTTP 服务入口：
 * 当前阶段仅提供健康检查；后续在 A4 增加 run 相关 API。
 */
export function createServer() {
  const app = Fastify({
    logger: true
  });

  app.get("/health", async () => {
    app.log.info("健康检查请求已处理");
    return { status: "ok" };
  });

  return app;
}

async function bootstrap() {
  const app = createServer();
  try {
    await app.listen({
      host: config.host,
      port: config.port
    });
    app.log.info(`Runner service listening at http://${config.host}:${config.port}`);
  } catch (error) {
    app.log.error(error, "Failed to start runner service");
    process.exit(1);
  }
}

bootstrap();
