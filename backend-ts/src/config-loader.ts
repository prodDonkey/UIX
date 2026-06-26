import { config as loadDotenv } from "dotenv";
import path from "node:path";

export function loadEnvFiles(projectRoot: string): void {
  const candidatePaths = [
    path.join(projectRoot, ".env"),
    path.join(path.dirname(projectRoot), ".env")
  ];

  for (const envPath of candidatePaths) {
    loadDotenv({
      path: envPath
    });
  }
}
