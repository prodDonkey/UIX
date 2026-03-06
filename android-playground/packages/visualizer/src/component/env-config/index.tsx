import { SettingOutlined } from '@ant-design/icons';
import { Input, Modal, Tooltip } from 'antd';
import { useEffect, useRef, useState } from 'react';
import { useEnvConfig } from '../../store/store';

export function EnvConfig({
  showTooltipWhenEmpty = true,
  showModelName = true,
  tooltipPlacement = 'bottom',
  mode = 'icon',
}: {
  showTooltipWhenEmpty?: boolean;
  showModelName?: boolean;
  tooltipPlacement?: 'bottom' | 'top';
  mode?: 'icon' | 'text';
}) {
  const { config, configString, loadConfig, syncFromStorage } = useEnvConfig();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [tempConfigString, setTempConfigString] = useState(configString);
  const midsceneModelName = config.MIDSCENE_MODEL_NAME;
  const componentRef = useRef<HTMLDivElement>(null);
  const showModal = (e: React.MouseEvent) => {
    // every time open modal, sync from localStorage
    syncFromStorage();

    setIsModalOpen(true);
    e.preventDefault();
    e.stopPropagation();
  };

  const handleOk = () => {
    setIsModalOpen(false);
    loadConfig(tempConfigString);
  };

  const handleCancel = () => {
    setIsModalOpen(false);
  };

  // when modal is open, use the latest config string
  useEffect(() => {
    if (isModalOpen) {
      setTempConfigString(configString);
    }
  }, [isModalOpen, configString]);

  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'flex-end',
        gap: '10px',
        alignItems: 'center',
        height: '100%',
        minHeight: '32px',
      }}
      ref={componentRef}
    >
      {showModelName ? midsceneModelName : null}
      <Tooltip
        title="使用前请先配置环境变量。"
        placement={tooltipPlacement}
        align={{ offset: [-10, 5] }}
        getPopupContainer={() => componentRef.current as HTMLElement}
        open={
          // undefined for default behavior of tooltip, hover for show
          // close tooltip when modal is open
          isModalOpen
            ? false
            : showTooltipWhenEmpty
              ? Object.keys(config).length === 0
              : undefined
        }
      >
        {mode === 'icon' ? (
          <SettingOutlined onClick={showModal} />
        ) : (
          <span
            onClick={showModal}
            style={{ color: '#006AFF', cursor: 'pointer' }}
          >
            去设置
          </span>
        )}
      </Tooltip>
      <Modal
        title="模型环境变量配置"
        open={isModalOpen}
        onOk={handleOk}
        onCancel={handleCancel}
        okText="保存"
        style={{ width: '800px', height: '100%', marginTop: '10%' }}
        destroyOnClose={true}
        maskClosable={true}
        centered={true}
      >
        <Input.TextArea
          rows={7}
          placeholder={
            'MIDSCENE_MODEL_API_KEY=sk-...\nMIDSCENE_MODEL_NAME=gpt-4o-2024-08-06\n...'
          }
          value={tempConfigString}
          onChange={(e) => setTempConfigString(e.target.value)}
          style={{ whiteSpace: 'nowrap', wordWrap: 'break-word' }}
        />
        <div>
          <p>格式为 `KEY=VALUE`，每行一项。</p>
          <p>
            这些配置会<strong>保存在当前浏览器本地</strong>。
          </p>
        </div>
      </Modal>
    </div>
  );
}
