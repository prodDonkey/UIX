import type { FastifyReply } from "fastify";

export class AppError extends Error {
  statusCode: number;
  detail: string;

  constructor(statusCode: number, detail: string) {
    super(detail);
    this.statusCode = statusCode;
    this.detail = detail;
  }
}

export function badRequest(detail: string): never {
  throw new AppError(400, detail);
}

export function notFound(detail: string): never {
  throw new AppError(404, detail);
}

export function conflict(detail: string): never {
  throw new AppError(409, detail);
}

export function sendError(reply: FastifyReply, error: unknown) {
  if (error instanceof AppError) {
    return reply.code(error.statusCode).send({ detail: error.detail });
  }

  if (error instanceof Error) {
    reply.log.error(error);
    return reply.code(500).send({ detail: error.message || "Internal Server Error" });
  }

  reply.log.error({ error }, "unknown route error");
  return reply.code(500).send({ detail: "Internal Server Error" });
}
