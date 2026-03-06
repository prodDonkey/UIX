import {
  ArrowRightOutlined,
  CheckOutlined,
  ClockCircleOutlined,
  CloseOutlined,
  LogoutOutlined,
  MinusOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import { Alert } from 'antd';
import type React from 'react';
import ShinyText from '../shiny-text';

export function timeCostStrElement(timeCost?: number) {
  let str: string;
  if (typeof timeCost !== 'number') {
    str = '-';
  } else {
    str = `${(timeCost / 1000).toFixed(2)}s`;
  }
  return (
    <span
      style={{
        fontVariantNumeric: 'tabular-nums',
        fontFeatureSettings: 'tnum',
      }}
    >
      {str}
    </span>
  );
}

export const iconForStatus = (status: string) => {
  switch (status) {
    case 'finished':
    case 'passed':
    case 'success':
    case 'connected':
      return (
        <span style={{ color: '#00AD4B' }}>
          <CheckOutlined />
        </span>
      );

    case 'finishedWithWarning':
      return (
        <span style={{ color: '#f7bb05' }}>
          <WarningOutlined />
        </span>
      );
    case 'failed':
    case 'closed':
    case 'timedOut':
    case 'interrupted':
      return (
        <span style={{ color: '#FF0A0A' }}>
          <CloseOutlined />
        </span>
      );
    case 'pending':
      return <ClockCircleOutlined />;
    case 'cancelled':
    case 'skipped':
      return <LogoutOutlined />;
    case 'running':
      return <ArrowRightOutlined />;
    default:
      return <MinusOutlined />;
  }
};

// server not ready error message
export const errorMessageServerNotReady = (
  <span>
    别担心，再完成一步就能启动 playground 服务。
    <br />
    请在 midscene 项目目录下执行以下任一命令：
    <br />
    a. <strong>npx midscene-playground</strong>
    <br />
    b. <strong>npx --yes @midscene/web</strong>
  </span>
);

// server launch tip
export const serverLaunchTip = (
  notReadyMessage: React.ReactNode | string = errorMessageServerNotReady,
) => (
  <div className="server-tip">
    <Alert
      message="Playground 服务未就绪"
      description={notReadyMessage}
      type="warning"
    />
  </div>
);

// empty result tip
export const emptyResultTip = (
  <div className="result-empty-tip" style={{ textAlign: 'center' }}>
    <ShinyText disabled text="执行结果会显示在这里" />
  </div>
);
