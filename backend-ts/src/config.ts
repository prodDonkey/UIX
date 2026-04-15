import path from "node:path";
import { fileURLToPath } from "node:url";
import { z } from "zod";
import { loadEnvFiles } from "./config-loader.js";

const currentDir = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(currentDir, "../..");

loadEnvFiles(projectRoot);

if (typeof process.env.DATABASE_URL === "string" && process.env.DATABASE_URL.startsWith("mysql+pymysql://")) {
  process.env.DATABASE_URL = process.env.DATABASE_URL.replace(/^mysql\+pymysql:\/\//, "mysql://");
}

const envSchema = z.object({
  APP_NAME: z.string().default("UI自动化脚本 API (TS)"),
  APP_ENV: z.string().default("dev"),
  PORT: z.coerce.number().default(8001),
  HOST: z.string().default("0.0.0.0"),
  DATABASE_URL: z.string().min(1, "DATABASE_URL is required"),
  SCENE_HTTP_TIMEOUT_SEC: z.coerce.number().default(30),
  MIDSCENE_ANDROID_DEVICE_ID: z.string().optional(),
  MIDSCENE_MODEL_NAME: z.string().optional(),
  MIDSCENE_MODEL_BASE_URL: z.string().optional(),
  MIDSCENE_MODEL_API_KEY: z.string().optional(),
  MIDSCENE_MODEL_FAMILY: z.string().optional(),
  LLM_MODEL_NAME: z.string().optional(),
  LLM_BASE_URL: z.string().optional(),
  LLM_API_KEY: z.string().optional(),
  LLM_MODEL_FAMILY: z.string().optional(),
  GETRESULT_COOKIE: z.string().optional(),
  GETRESULT_UID: z.string().optional(),
  GETRESULT_ADDRESS_ID: z.string().optional(),
  GETRESULT_APPOINTMENT_TIME: z.string().optional()
});

export const env = envSchema.parse(process.env);
