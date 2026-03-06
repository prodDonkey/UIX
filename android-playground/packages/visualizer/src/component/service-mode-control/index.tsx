import { PlaygroundSDK } from '@midscene/playground';
import { Button, Tooltip, message } from 'antd';
import type React from 'react';
import { useEffect } from 'react';
import { safeOverrideAIConfig } from '../../hooks/useSafeOverrideAIConfig';
import { useServerValid } from '../../hooks/useServerValid';
import { useEnvConfig } from '../../store/store';
import { EnvConfig } from '../env-config';
import { iconForStatus } from '../misc';
interface ServiceModeControlProps {
  serviceMode: 'Server' | 'In-Browser';
}

// Centralized text constants
const TITLE_TEXT = {
  Server: '服务状态',
  'In-Browser': '浏览器内模式',
};

const SWITCH_BUTTON_TEXT = {
  Server: '切换到浏览器内模式',
  'In-Browser': '切换到服务端模式',
};

export const ServiceModeControl: React.FC<ServiceModeControlProps> = ({
  serviceMode,
}) => {
  const { setServiceMode, config } = useEnvConfig();
  const serverValid = useServerValid(serviceMode === 'Server');

  // Render server tip based on connection status
  const renderServerTip = () => {
    if (serverValid) {
      return (
        <Tooltip title="已连接">
          <div className="server-tip">{iconForStatus('connected')}</div>
        </Tooltip>
      );
    }
    return (
      <Tooltip title="连接失败">
        <div className="server-tip">{iconForStatus('failed')}</div>
      </Tooltip>
    );
  };

  // Render switch button if not in extension mode
  const renderSwitchButton = () => {
    const nextMode = serviceMode === 'Server' ? 'In-Browser' : 'Server';
    const buttonText = SWITCH_BUTTON_TEXT[serviceMode];

    return (
      <Tooltip
        title={
          <span>
            服务端模式：通过服务端转发请求 <br />
            浏览器内模式：通过浏览器 fetch API 直接请求（此时 AI 服务需支持
            CORS）
          </span>
        }
      >
        <Button
          type="link"
          onClick={(e) => {
            e.preventDefault();
            setServiceMode(nextMode);
          }}
        >
          {buttonText}
        </Button>
      </Tooltip>
    );
  };

  useEffect(() => {
    safeOverrideAIConfig(config, false, false); // Don't show error message in this component
    if (serviceMode === 'Server') {
      const playgroundSDK = new PlaygroundSDK({
        type: 'remote-execution',
      });
      playgroundSDK.overrideConfig(config).catch((error) => {
        const errorMsg = error instanceof Error ? error.message : String(error);
        message.error(`应用 AI 配置失败：${errorMsg}`);
      });
    }
  }, [config, serviceMode, serverValid]);

  // Determine content based on service mode
  const statusContent = serviceMode === 'Server' && renderServerTip();
  const title = TITLE_TEXT[serviceMode];

  return (
    <>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '10px',
        }}
      >
        <h3
          style={{
            whiteSpace: 'nowrap',
            margin: 0,
            flexShrink: 0,
          }}
        >
          {title}
        </h3>
        {statusContent}
        <EnvConfig showTooltipWhenEmpty={serviceMode !== 'Server'} />
      </div>

      <div className="switch-btn-wrapper">{renderSwitchButton()}</div>
    </>
  );
};
