import type { UIContext } from '@midscene/core';
import { StaticPage, StaticPageAgent } from '@midscene/web/static';
import type { ZodObjectSchema } from '../types';
import { isZodObjectSchema, unwrapZodType } from '../types';

// Get action name based on type
export const actionNameForType = (type: string) => {
  if (!type) return '';
  const nameMap: Record<string, string> = {
    aiAct: '执行',
    runYaml: 'YAML 脚本',
    aiTap: '点击',
    aiDoubleClick: '双击',
    aiHover: '悬停',
    aiInput: '输入',
    aiRightClick: '右键',
    aiKeyboardPress: '按键',
    aiScroll: '滚动',
    aiLocate: '定位',
    aiQuery: '查询',
    aiBoolean: '布尔值',
    aiNumber: '数值',
    aiString: '文本',
    aiAsk: '提问',
    aiAssert: '断言',
    aiWaitFor: '等待',
    launch: '启动',
    runAdbShell: '执行 ADB 命令',
    AndroidBackButton: '系统返回',
    AndroidHomeButton: '回到桌面',
    AndroidRecentAppsButton: '最近任务',
  };

  if (nameMap[type]) {
    return nameMap[type];
  }

  // Remove 'ai' prefix and convert camelCase to space-separated words
  const typeWithoutAi = type.startsWith('ai') ? type.slice(2) : type;

  // Special handling for iOS-specific actions to preserve their full names
  if (typeWithoutAi.startsWith('IOS')) {
    // For IOS actions, keep IOS as a unit and add spaces before remaining capital letters
    return typeWithoutAi
      .substring(3)
      .replace(/([A-Z])/g, ' $1')
      .replace(/^/, 'IOS')
      .trim();
  }

  const fullName = typeWithoutAi.replace(/([A-Z])/g, ' $1').trim();

  // For long names, keep the last 3 words to make them shorter
  const words = fullName.split(' ');
  if (words.length > 3) {
    return words.slice(-3).join(' ');
  }

  return fullName;
};

// Create static agent from context
export const staticAgentFromContext = (context: UIContext) => {
  const page = new StaticPage(context);
  return new StaticPageAgent(page);
};

// Get placeholder text based on run type
export const getPlaceholderForType = (type: string): string => {
  if (type === 'runYaml') {
    return '请输入 Midscene YAML 脚本内容（tasks: ...）';
  }
  if (type === 'aiQuery') {
    return '你想查询什么？';
  }
  if (type === 'aiAssert') {
    return '你想断言什么？';
  }
  if (type === 'aiTap') {
    return '你想点击哪个元素？';
  }
  if (type === 'aiDoubleClick') {
    return '你想双击哪个元素？';
  }
  if (type === 'aiHover') {
    return '你想悬停在哪个元素上？';
  }
  if (type === 'aiInput') {
    return '格式：<内容> | <元素>\n示例：hello world | 搜索框';
  }
  if (type === 'aiRightClick') {
    return '你想右键哪个元素？';
  }
  if (type === 'aiKeyboardPress') {
    return '格式：<按键> | <元素（可选）>\n示例：Enter | 输入框';
  }
  if (type === 'aiScroll') {
    return '格式：<方向> <距离> | <元素（可选）>\n示例：down 500 | 主内容区域';
  }
  if (type === 'aiLocate') {
    return '你想定位哪个元素？';
  }
  if (type === 'aiBoolean') {
    return '你想检查什么（返回 true/false）？';
  }
  if (type === 'aiNumber') {
    return '你想提取哪个数值？';
  }
  if (type === 'aiString') {
    return '你想提取哪段文本？';
  }
  if (type === 'aiAsk') {
    return '你想提什么问题？';
  }
  if (type === 'aiWaitFor') {
    return '你想等待什么条件成立？';
  }
  return '你想执行什么操作？';
};

export const isRunButtonEnabled = (
  runButtonEnabled: boolean,
  needsStructuredParams: boolean,
  params: any,
  actionSpace: any[] | undefined,
  selectedType: string,
  promptValue: string,
) => {
  if (!runButtonEnabled) {
    return false;
  }

  // Check if this method needs any input
  const needsAnyInput = (() => {
    if (actionSpace) {
      // Use actionSpace to determine if method needs any input
      const action = actionSpace.find(
        (a) => a.interfaceAlias === selectedType || a.name === selectedType,
      );

      // If action exists in actionSpace, check if it has paramSchema with actual fields
      if (action) {
        if (!action.paramSchema) return false;

        // Check if paramSchema actually has fields
        if (
          typeof action.paramSchema === 'object' &&
          'shape' in action.paramSchema
        ) {
          const shape =
            (action.paramSchema as { shape: Record<string, unknown> }).shape ||
            {};
          const shapeKeys = Object.keys(shape);
          return shapeKeys.length > 0; // Only need input if there are actual fields
        }

        // If paramSchema exists but not in expected format, assume it needs input
        return true;
      }

      // If not found in actionSpace, assume most methods need input
      return true;
    }

    // Fallback: most methods need some input
    return true;
  })();

  // If method doesn't need any input, button is always enabled (when runButtonEnabled is true)
  if (!needsAnyInput) {
    return true;
  }

  if (needsStructuredParams) {
    const currentParams = params || {};
    const action = actionSpace?.find(
      (a) => a.interfaceAlias === selectedType || a.name === selectedType,
    );
    if (action?.paramSchema && isZodObjectSchema(action.paramSchema)) {
      // Check if all required fields are filled
      const schema = action.paramSchema as unknown as ZodObjectSchema;
      const shape = schema.shape || {};
      return Object.keys(shape).every((key) => {
        const field = shape[key];
        const { isOptional } = unwrapZodType(field);
        const value = currentParams[key];
        // A field is valid if it's optional or has a non-empty value
        return (
          isOptional || (value !== undefined && value !== '' && value !== null)
        );
      });
    }
    return true; // Fallback for safety
  }
  return promptValue.trim().length > 0;
};
