type RuntimeConfig = {
  API_BASE_URL?: string;
  ANDROID_PLAYGROUND_URL?: string;
};

function readRuntimeConfig(): RuntimeConfig {
  const runtimeWindow = window as typeof window & {
    __APP_CONFIG__?: RuntimeConfig;
  };
  return runtimeWindow.__APP_CONFIG__ ?? {};
}

export function getApiBaseUrl(): string {
  const runtimeConfig = readRuntimeConfig();
  return runtimeConfig.API_BASE_URL || import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
}

export function getAndroidPlaygroundUrl(): string {
  const runtimeConfig = readRuntimeConfig();
  return (
    runtimeConfig.ANDROID_PLAYGROUND_URL ||
    import.meta.env.VITE_ANDROID_PLAYGROUND_URL ||
    'http://localhost:5800'
  );
}
