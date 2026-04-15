type RuntimeConfig = {
  API_BASE_URL?: string;
};

function readRuntimeConfig(): RuntimeConfig {
  const runtimeWindow = window as typeof window & {
    __APP_CONFIG__?: RuntimeConfig;
  };
  return runtimeWindow.__APP_CONFIG__ ?? {};
}

export function getApiBaseUrl(): string {
  const runtimeConfig = readRuntimeConfig();
  if (runtimeConfig.API_BASE_URL !== undefined) return runtimeConfig.API_BASE_URL;
  if (import.meta.env.VITE_API_BASE_URL !== undefined) return import.meta.env.VITE_API_BASE_URL;
  return 'http://127.0.0.1:8001';
}
