import { env } from "./config.js";
import { createServer } from "./server.js";

async function main() {
  const app = createServer();

  try {
    await app.listen({
      host: env.HOST,
      port: env.PORT
    });
  } catch (error) {
    app.log.error(error);
    process.exitCode = 1;
  }
}

void main();
