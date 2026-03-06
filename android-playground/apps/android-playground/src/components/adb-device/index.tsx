import './index.less';
import { MobileOutlined } from '@ant-design/icons';
import { useServerValid } from '@midscene/visualizer';
import { message } from 'antd';
import { useCallback } from 'react';
import type { RefObject } from 'react';
import type { ScrcpyRefMethods } from '../scrcpy-player';

// status dot indicator
const onlineStatus = (color: string) => (
  <span
    className="status-dot"
    style={{
      color: color,
    }}
  >
    ●
  </span>
);

export interface Device {
  id: string;
  name: string;
  status: string;
}

export interface AdbDeviceProps {
  selectedDeviceId: string | null;
  scrcpyPlayerRef: RefObject<ScrcpyRefMethods>;
}

const AdbDevice: React.FC<AdbDeviceProps> = ({
  selectedDeviceId,
  scrcpyPlayerRef,
}) => {
  const [messageApi, contextHolder] = message.useMessage();
  const serverValid = useServerValid(true);

  // disconnect device
  const disconnectDevice = useCallback(() => {
    // call ScrcpyPlayer's disconnectDevice method
    if (scrcpyPlayerRef.current) {
      scrcpyPlayerRef.current.disconnectDevice();
      messageApi.info('设备已断开连接');
    }
  }, [scrcpyPlayerRef, messageApi]);

  return (
    <div className="device-header">
      {contextHolder}
      <div className="device-title-container">
        <h2 className="device-title">设备</h2>
        <div className="device-info-display">
          <div className="device-icon-container">
            <MobileOutlined className="device-icon" />
            {selectedDeviceId && serverValid && (
              <div className="status-indicator">{onlineStatus('#52c41a')}</div>
            )}
          </div>
          {selectedDeviceId ? (
            <span className="device-name">{selectedDeviceId}</span>
          ) : (
            <span className="device-name no-device">未选择设备</span>
          )}
        </div>
      </div>
    </div>
  );
};

export default AdbDevice;
