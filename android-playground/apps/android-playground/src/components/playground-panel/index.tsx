import { PlaygroundSDK } from '@midscene/playground';
import { PLAYGROUND_SERVER_PORT } from '@midscene/shared/constants';
import {
  UniversalPlayground,
  useEnvConfig,
} from '@midscene/visualizer';
import { useEffect, useMemo } from 'react';
import './index.less';

declare const __APP_VERSION__: string;

/**
 * Playground panel component for Android Playground using Universal Playground
 * Replaces the left panel with form and results
 */
export default function PlaygroundPanel() {
  // Get config from the global state
  const { config } = useEnvConfig();

  // Initialize PlaygroundSDK for remote execution
  const playgroundSDK = useMemo(() => {
    const defaultServerUrl = `http://${window.location.hostname}:${PLAYGROUND_SERVER_PORT}`;
    const serverUrl =
      (window as any).PLAYGROUND_SERVER_URL || defaultServerUrl;

    return new PlaygroundSDK({
      type: 'remote-execution',
      serverUrl,
    });
  }, []);

  // Check server status on mount to initialize SDK ID
  useEffect(() => {
    const checkServer = async () => {
      try {
        const online = await playgroundSDK.checkStatus();
        console.log(
          '[DEBUG] Android playground server status:',
          online,
          'ID:',
          playgroundSDK.id,
        );
      } catch (error) {
        console.error(
          'Failed to check android playground server status:',
          error,
        );
      }
    };

    checkServer();
  }, [playgroundSDK]);

  // Override SDK config when configuration changes
  useEffect(() => {
    if (playgroundSDK.overrideConfig && config) {
      playgroundSDK.overrideConfig(config).catch((error) => {
        console.error('Failed to override SDK config:', error);
      });
    }
  }, [playgroundSDK, config]);

  return (
    <div className="playground-panel">
      <div className="playground-panel-playground">
        <UniversalPlayground
          playgroundSDK={playgroundSDK}
          config={{
            showContextPreview: false,
            layout: 'vertical',
            showVersionInfo: false,
            enableScrollToBottom: true,
            serverMode: true,
            showEnvConfigReminder: true,
            deviceType: 'android',
            disableAutoLoadHistory: true,
          }}
          branding={{
            title: '安卓调试台',
            version: __APP_VERSION__,
          }}
          className="playground-container"
        />
      </div>
    </div>
  );
}
