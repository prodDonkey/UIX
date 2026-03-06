import { InfoCircleOutlined, ReloadOutlined } from '@ant-design/icons';
import { Button, Spin, Tooltip } from 'antd';
import { useCallback, useEffect, useRef, useState } from 'react';
import './index.less';

interface ScreenshotViewerProps {
  getScreenshot: () => Promise<{
    screenshot: string;
    timestamp: number;
  } | null>;
  getInterfaceInfo?: () => Promise<{
    type: string;
    description?: string;
  } | null>;
  serverOnline: boolean;
  isUserOperating?: boolean; // Whether user is currently operating
  mjpegUrl?: string; // When provided, use MJPEG live stream instead of polling
}

export default function ScreenshotViewer({
  getScreenshot,
  getInterfaceInfo,
  serverOnline,
  isUserOperating = false,
  mjpegUrl,
}: ScreenshotViewerProps) {
  const [screenshot, setScreenshot] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdateTime, setLastUpdateTime] = useState<number>(0);
  const [interfaceInfo, setInterfaceInfo] = useState<{
    type: string;
    description?: string;
  } | null>(null);
  const isMjpeg = Boolean(mjpegUrl && serverOnline);

  // Refs for managing polling
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const isPollingPausedRef = useRef(false);

  // Core function to fetch screenshot
  const fetchScreenshot = useCallback(
    async (isManual = false) => {
      if (!serverOnline) return;

      setLoading(true);
      if (isManual) setError(null); // Clear errors on manual refresh

      try {
        const result = await getScreenshot();
        console.log('Screenshot API response:', result); // Debug log

        if (result?.screenshot) {
          // Ensure screenshot is a valid string
          const screenshotData = result.screenshot.toString().trim();
          if (screenshotData) {
            // Screenshot data is already in full data URL format from createImgBase64ByFormat
            setScreenshot(screenshotData);
            setError(null); // Clear any previous errors
            setLastUpdateTime(Date.now());
          } else {
            setError('收到的截图数据为空');
          }
        } else {
          setError('响应中未包含截图数据');
        }
      } catch (err) {
        console.error('Screenshot fetch error:', err); // Debug log
        setError(
          err instanceof Error ? err.message : '获取截图失败',
        );
      } finally {
        setLoading(false);
      }
    },
    [getScreenshot, serverOnline],
  );

  // Function to fetch interface info
  const fetchInterfaceInfo = useCallback(async () => {
    if (!serverOnline || !getInterfaceInfo) return;

    try {
      const info = await getInterfaceInfo();
      if (info) {
        setInterfaceInfo(info);
      }
    } catch (err) {
      console.error('Interface info fetch error:', err);
    }
  }, [getInterfaceInfo, serverOnline]);

  // Start polling
  const startPolling = useCallback(() => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
    }

    console.log('Starting screenshot polling (5s interval)');
    pollingIntervalRef.current = setInterval(() => {
      if (!isPollingPausedRef.current && serverOnline) {
        fetchScreenshot(false);
      }
    }, 5000); // 5 second polling
  }, [fetchScreenshot, serverOnline]);

  // Stop polling
  const stopPolling = useCallback(() => {
    if (pollingIntervalRef.current) {
      console.log('Stopping screenshot polling');
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
  }, []);

  // Pause polling (don't clear interval, just mark as paused)
  const pausePolling = useCallback(() => {
    console.log('Pausing screenshot polling');
    isPollingPausedRef.current = true;
  }, []);

  // Resume polling
  const resumePolling = useCallback(() => {
    console.log('Resuming screenshot polling');
    isPollingPausedRef.current = false;
  }, []);

  const handleManualRefresh = useCallback(() => {
    fetchScreenshot(true);
  }, [fetchScreenshot]);

  // Manage server connection status changes
  useEffect(() => {
    if (!serverOnline) {
      setScreenshot(null);
      setError(null);
      setInterfaceInfo(null);
      stopPolling();
      return;
    }

    // Fetch interface info regardless of mode
    fetchInterfaceInfo();

    // In MJPEG mode, skip polling entirely
    if (isMjpeg) {
      stopPolling();
      return;
    }

    // When server comes online, fetch screenshot and interface info immediately, then start polling
    fetchScreenshot(false);
    startPolling();

    return () => {
      stopPolling();
    };
  }, [
    serverOnline,
    isMjpeg,
    startPolling,
    stopPolling,
    fetchScreenshot,
    fetchInterfaceInfo,
  ]);

  // Manage user operation status changes
  useEffect(() => {
    if (!serverOnline) return;

    if (isUserOperating) {
      // When user starts operating, pause polling
      pausePolling();
    } else {
      // When user operation ends, update screenshot immediately and resume polling
      resumePolling();
      fetchScreenshot(false);
    }
  }, [
    isUserOperating,
    pausePolling,
    resumePolling,
    fetchScreenshot,
    serverOnline,
  ]);

  // Cleanup function
  useEffect(() => {
    return () => {
      stopPolling();
    };
  }, [stopPolling]);

  if (!serverOnline) {
    return (
      <div className="screenshot-viewer offline">
        <div className="screenshot-placeholder">
          <h3>📱 屏幕预览</h3>
          <p>请先启动 Playground 服务以查看实时截图</p>
        </div>
      </div>
    );
  }

  if (!isMjpeg && loading && !screenshot) {
    return (
      <div className="screenshot-viewer loading">
        <Spin size="large" />
        <p>截图加载中...</p>
      </div>
    );
  }

  if (!isMjpeg && error && !screenshot) {
    return (
      <div className="screenshot-viewer error">
        <div className="screenshot-placeholder">
          <h3>📱 屏幕预览</h3>
          <p className="error-message">{error}</p>
        </div>
      </div>
    );
  }

  const formatLastUpdateTime = (timestamp: number) => {
    if (!timestamp) return '';
    const now = Date.now();
    const diff = Math.floor((now - timestamp) / 1000);

    if (diff < 60) return `${diff}秒前`;
    if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`;
    return new Date(timestamp).toLocaleTimeString();
  };

  return (
    <div className="screenshot-viewer">
      <div className="screenshot-header">
        <div className="screenshot-title">
          <h3>{interfaceInfo?.type ? interfaceInfo.type : '设备名称'}</h3>
        </div>
      </div>
      <div className="screenshot-container">
        <div className="screenshot-overlay">
          <div className="device-name-overlay">
            设备名称
            <Tooltip title={interfaceInfo?.description}>
              <InfoCircleOutlined size={16} className="info-icon" />
            </Tooltip>
          </div>
          {!isMjpeg && (
            <div className="screenshot-controls">
              {lastUpdateTime > 0 && (
                <span className="last-update-time">
                  最近更新：{formatLastUpdateTime(lastUpdateTime)}
                </span>
              )}
              <Tooltip title="刷新截图">
                <Button
                  icon={<ReloadOutlined />}
                  onClick={handleManualRefresh}
                  loading={loading}
                  size="small"
                />
              </Tooltip>
              {isUserOperating && (
                <span className="operation-indicator">
                  <Spin size="small" /> 正在操作...
                </span>
              )}
            </div>
          )}
        </div>
        <div className="screenshot-content">
          {isMjpeg ? (
            <img
              src={mjpegUrl}
              alt="设备实时画面"
              className="screenshot-image"
            />
          ) : screenshot ? (
            <img
              src={
                screenshot.startsWith('data:image/')
                  ? screenshot
                  : `data:image/png;base64,${screenshot}`
              }
              alt="设备截图"
              className="screenshot-image"
              onLoad={() => console.log('Screenshot image loaded successfully')}
              onError={(e) => {
                console.error('Screenshot image load error:', e);
                console.error(
                  'Screenshot data preview:',
                  screenshot.substring(0, 100),
                );
                setError('截图图片加载失败');
              }}
            />
          ) : (
            <div className="screenshot-placeholder">
              <p>暂无可用截图</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
