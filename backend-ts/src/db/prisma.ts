import "../config.js";

import { PrismaClient } from "@prisma/client";

declare global {
  // eslint-disable-next-line no-var
  var __uixPrisma__: PrismaClient | undefined;
}

export const prisma =
  globalThis.__uixPrisma__ ??
  new PrismaClient({
    log: process.env.APP_ENV === "dev" ? ["warn", "error"] : ["error"]
  });

if (process.env.NODE_ENV !== "production") {
  globalThis.__uixPrisma__ = prisma;
}
