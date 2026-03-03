# Midscene YAML 指令词典（LLM 学习版）

来源：
- https://midscenejs.com/zh/automate-with-scripts-in-yaml.html
- https://midscenejs.com/zh/api.html

适用目标：
- 让 LLM 按统一结构稳定生成可执行 YAML。
- 文档顺序对齐官方：`agent` → `android` → `tasks`。

## 1. `agent` 部分词典

用途：
- 配置报告、重规划、全局上下文、缓存等通用能力。

模板：

```yaml
agent:
  testId: <string>
  groupName: <string>
  groupDescription: <string>
  generateReport: <boolean>
  autoPrintReportMsg: <boolean>
  reportFileName: <string>
  replanningCycleLimit: <number>
  aiActContext: <string>
  cache:
    strategy: read-only | read-write | write-only
    id: <string>
```

字段说明：
- `testId: string` # 测试 ID；优先级为 CLI > agent.testId > 文件名
- `groupName: string` # 报告中的分组名称
- `groupDescription: string` # 分组描述
- `generateReport: boolean` # 是否生成 HTML 报告（默认 true）
- `autoPrintReportMsg: boolean` # 是否自动打印报告路径（默认 true）
- `reportFileName: string` # 报告文件名
- `replanningCycleLimit: number` # 重规划轮数上限（默认 20，UI-TARS 为 40）
- `aiActContext: string` # 给动作规划的全局上下文
- `cache.strategy: enum` # 缓存策略：read-only/read-write/write-only
- `cache.id: string` # 缓存 ID（启用缓存时必填）

兼容字段：
- `aiActionContext: string` # 旧字段，仍兼容；建议统一用 `aiActContext`

示例：

```yaml
agent:
  testId: checkout-test
  groupName: E2E 测试套件
  groupDescription: 完整购物流程测试
  generateReport: true
  autoPrintReportMsg: false
  reportFileName: checkout-report
  replanningCycleLimit: 30
  aiActContext: 出现弹窗先点击同意
  cache:
    strategy: read-write
    id: checkout-cache
```

## 2. `android` 部分词典

用途：
- 指定 Android 设备与运行配置。

模板：

```yaml
android:
  deviceId: <device-id>
  launch: <url-or-app>
  output: <path-to-output-file>
```

字段说明：
- `deviceId: string` # 设备 ID；不填默认首个连接设备
- `launch: string` # 启动 URL/包名/Activity；不填默认当前页面
- `output: string` # 输出 aiQuery/aiAssert 结果 JSON 路径

常见扩展字段（AndroidDevice 参数）：
- `androidAdbPath` # 自定义 adb 可执行文件路径
- `remoteAdbHost` # 远程 adb server 主机
- `remoteAdbPort` # 远程 adb server 端口
- `imeStrategy` # 输入策略（何时使用 yadb）
- `displayId` # 多屏场景目标屏幕 ID
- `autoDismissKeyboard` # 输入后是否自动收起键盘
- `keyboardDismissStrategy` # 收键盘策略（esc-first/back-first）
- `screenshotResizeScale` # 截图缩放比例
- `alwaysRefreshScreenInfo` # 每步是否刷新屏幕信息

示例：

```yaml
android:
  deviceId: emulator-5554
  launch: com.android.settings
  output: ./result.json
```

常用 ADB Shell 命令：
- `pm clear <package>` - 清除应用数据
- `dumpsys battery` - 获取电池信息
- `dumpsys window` - 获取窗口信息
- `settings get secure android_id` - 获取设备 ID
- `input keyevent <keycode>` - 发送按键事件

## 3. `tasks` 部分词典

### 3.1 结构

```yaml
tasks:
  - name: <name>
    continueOnError: <boolean>
    flow:
      - <step>
```

字段说明：
- `name: string` # 任务名（必填）
- `continueOnError: boolean` # 当前 task 失败后是否继续后续 task（默认 false）
- `flow: array` # 步骤数组（必填）

### 3.2 flow：自动规划类

#### `ai`
- 含义：执行自然语言交互；是 `aiAct` 简写。
- 可选参数：
- `cacheable: boolean` # 是否允许缓存当前步骤结果（默认 true）
- `deepThink: boolean` # 是否开启更深层思考定位（复杂场景可开启）

```yaml
- ai: 在搜索框输入“深圳北站”并点击搜索
```

#### `aiAct`
- 含义：与 `ai` 等价。
- 可选参数：
- `cacheable: boolean` # 是否允许缓存当前步骤结果（默认 true）
- `deepThink: boolean` # 是否开启更深层思考定位（复杂场景可开启）

```yaml
- aiAct: 勾选已阅读并同意，然后点击登录
```

#### `aiAction`（兼容）
- 含义：旧写法，保留兼容。
- 建议：新脚本统一使用 `ai` 或 `aiAct`。

### 3.3 flow：即时动作类

#### `aiTap`
- 含义：点击元素。
- 可选参数：
- `deepThink: boolean` # 是否开启更深层思考定位（复杂场景可开启）
- `xpath: string` # 指定元素 XPath，提供后优先按 XPath 定位
- `cacheable: boolean` # 是否允许缓存当前步骤结果（默认 true）

```yaml
- aiTap: 点击“登录”按钮
```

#### `aiHover`
- 含义：悬停元素（Web 常见）。
- 可选参数：
- `deepThink: boolean` # 是否开启更深层思考定位（复杂场景可开启）
- `xpath: string` # 指定元素 XPath，提供后优先按 XPath 定位
- `cacheable: boolean` # 是否允许缓存当前步骤结果（默认 true）

```yaml
- aiHover: 悬停用户头像
```

#### `aiInput`
- 含义：向目标元素输入文本。
- 必填参数：
- `value: string` # 输入框最终文本内容
- 可选参数：
- `deepThink: boolean` # 是否开启更深层思考定位（复杂场景可开启）
- `xpath: string` # 指定元素 XPath，提供后优先按 XPath 定位
- `cacheable: boolean` # 是否允许缓存当前步骤结果（默认 true）

```yaml
- aiInput: 手机号输入框
  value: "13188888888"
```

#### `aiKeyboardPress`
- 含义：在目标元素上按键（Enter/Tab/Escape 等）。
- 必填参数：
- `keyName: string` # 按键名，例如 Enter/Tab/Escape
- 可选参数：
- `deepThink: boolean` # 是否开启更深层思考定位（复杂场景可开启）
- `xpath: string` # 指定元素 XPath，提供后优先按 XPath 定位
- `cacheable: boolean` # 是否允许缓存当前步骤结果（默认 true）

```yaml
- aiKeyboardPress: 搜索输入框
  keyName: Enter
```

#### `aiScroll`
- 含义：全局或局部滚动。
- 可选参数：
- `scrollType: singleAction | scrollToBottom | scrollToTop | scrollToRight | scrollToLeft` # 滚动模式
- `direction: down | up | left | right` # 滚动方向（仅 singleAction 生效）
- `distance: number | null` # 滚动距离（像素），null 表示自动决定
- `deepThink: boolean` # 是否开启更深层思考定位（复杂场景可开启）
- `xpath: string` # 指定元素 XPath，提供后优先按 XPath 定位
- `cacheable: boolean` # 是否允许缓存当前步骤结果（默认 true）

```yaml
- aiScroll: 商品列表
  scrollType: singleAction
  direction: down
```

### 3.4 flow：查询/断言/等待

#### `aiQuery`
- 含义：提取结构化数据。
- 可选参数：
- `name: string` # 结果在输出 JSON 中的 key 名

```yaml
- aiQuery: "提取商品列表，格式：[{name: string, price: string}]"
  name: products
```

#### `aiWaitFor`
- 含义：等待条件满足。
- 可选参数：
- `timeout: number` # 等待超时毫秒（默认 30000）

```yaml
- aiWaitFor: 页面出现“首页”
  timeout: 30000
```

#### `aiAssert`
- 含义：断言条件成立。
- 可选参数：
- `errorMessage: string` # 断言失败时的自定义错误信息
- `name: string` # 结果在输出 JSON 中的 key 名

```yaml
- aiAssert: 页面显示“登录成功”
  errorMessage: 登录后未进入首页
```

### 3.5 flow：通用辅助

#### `sleep`
- 含义：固定等待（毫秒）。

```yaml
- sleep: 1500
```

#### `recordToReport`
- 含义：记录截图到报告。
- 可选参数：
- `content: string` # 报告截图描述文字

```yaml
- recordToReport: 登录前页面
  content: 已输入手机号和验证码
```

#### `javascript`（Web 为主）
- 含义：在 Web 页面上下文执行 JS。
- 可选参数：
- `name: string` # 结果在输出 JSON 中的 key 名

```yaml
- javascript: return document.title
  name: pageTitle
```

### 3.6 flow：Android 特定动作

#### `runAdbShell`
- 含义：执行 adb shell 命令。

```yaml
- runAdbShell: dumpsys battery
```

#### `launch`
- 含义：启动 App 或 URL。

```yaml
- launch: com.android.settings
- launch: https://www.example.com
```

## 4. 图像提示（Prompt With Images）

用途：
- 对“无文字控件”增强定位（图标、圆形勾选框等）。

```yaml
- aiTap:
    locate:
      prompt: 点击左下角“已阅读并同意”的圆形勾选框
      images:
        - name: 勾选框参考图
          url: https://example.com/agree-checkbox.png
      convertHttpImage2Base64: true
```

字段说明：
- `prompt: string` # 文本描述
- `images: array` # 参考图列表（name + url）
- `convertHttpImage2Base64: boolean` # 远程图片不可直连时转 base64

## 5. 生成约束（建议固定放 System Prompt）

- 只输出 YAML 本体，不要 Markdown 代码块。
- 根节点必须是对象。
- Android 场景必须包含 `android` 与非空 `tasks`。
- 每个 task 必须有 `name` 和 `flow`。
- 优先 `ai/aiAct`，不稳定步骤用 `aiTap/aiInput/aiKeyboardPress`。
- 关键节点补 `aiWaitFor + aiAssert`。
- 未提供 `deviceId` 时不要编造 `android.deviceId`。

## 6. 常见错误

- 输出被包在 ```yaml 代码块。
- 缺 `tasks` 或 `tasks` 为空。
- task 缺少 `flow`。
- `aiInput` 漏写 `value`。
- 新脚本继续使用 `aiAction`。
- Android 脚本混入过多 Web 专属逻辑（如大量 `javascript`）。
