# Midscene API/YAML 语法整理（面向 Android 脚本生成）

> 基于官方文档整理：
> - https://midscenejs.com/zh/api.html
> - https://midscenejs.com/zh/automate-with-scripts-in-yaml.html
> - https://midscenejs.com/zh/android-api-reference.html

## 1. YAML 顶层结构

```yaml
agent:
  # 可选，通用配置（报告、缓存、上下文等）

android:
  # Android 设备与运行配置

tasks:
  - name: 任务名
    flow:
      - ai: ...
```

生成脚本时建议至少满足：
- 顶层是对象。
- 包含 `android`（对象）与 `tasks`（非空数组）。
- 每个 task 至少包含 `name` 与 `flow`。

## 2. `tasks[].flow` 常用指令

### 2.1 自动规划类（推荐优先）

- `ai`: `aiAct` 的简写。
- `aiAct`: 当前推荐名称。
- `aiAction`: 旧名称，兼容但不建议新脚本继续使用。

示例：

```yaml
- ai: 打开登录页，输入手机号并点击登录
```

可选参数（对象写法时）：
- `cacheable`
- `deepThink`（取决于模型家族能力）

### 2.2 即时操作类（原子动作）

- `aiTap`
- `aiHover`
- `aiInput`（通常配 `value`）
- `aiKeyboardPress`（通常配 `keyName`）
- `aiScroll`（可配 `scrollType`、`direction`、`distance`）

说明：
- 这类动作用于明确、可控的单步交互。
- 适合点击圆形勾选框、特定输入框、固定按钮等场景。

### 2.3 查询/断言/等待

- `aiQuery`: 从页面提取结构化信息（建议在 prompt 中写清返回 JSON 结构）。
- `aiAssert`: 断言页面状态，不满足会报错。
- `aiWaitFor`: 等待条件满足，可配 `timeout`（毫秒）。

### 2.4 通用辅助

- `sleep`: 固定等待（毫秒）。
- `javascript`: 执行 JS（主要用于 Web 场景）。
- `recordToReport`: 写入报告截图/描述。

## 3. Android 专属配置与动作

### 3.1 `android` 配置

```yaml
android:
  deviceId: emulator-5554 # 可选，不填默认首个连接设备
  launch: com.example.app # 可选，也可填 URL
  output: ./result.json    # 可选，输出 aiQuery/aiAssert 结果
```

`android` 还支持 `AndroidDevice` 构造函数的大部分参数，例如：
- `androidAdbPath`
- `remoteAdbHost` / `remoteAdbPort`
- `imeStrategy`
- `displayId`
- `autoDismissKeyboard`
- `keyboardDismissStrategy`
- `screenshotResizeScale`
- `alwaysRefreshScreenInfo`

### 3.2 Android flow 特定动作

- `launch`: 启动应用包名 / Activity / URL。
- `runAdbShell`: 执行 adb shell 命令。

示例：

```yaml
- launch: com.android.settings
- runAdbShell: dumpsys battery
```

## 4. `agent` 常见字段（跨平台）

```yaml
agent:
  testId: shangmenchaoren-login
  generateReport: true
  reportFileName: shangmenchaoren-login
  aiActContext: 出现权限弹窗或协议弹窗时优先点击同意
```

常见字段：
- `generateReport`
- `reportFileName`
- `aiActContext`（旧名 `aiActionContext` 仍兼容）
- `cache`（`id` + `strategy`）

## 5. 适合 LLM 生成 YAML 的约束模板

给模型的约束建议：
- 只输出 YAML，不要 Markdown 代码块，不要解释。
- 优先使用 `ai`/`aiAct`，必要时结合 `aiTap`/`aiInput` 提高稳定性。
- 若提供了 `deviceId`，写入 `android.deviceId`；未提供则不强行编造。
- 每个 task 的步骤尽量短小、单一意图。
- 对关键节点加 `aiAssert` 或 `aiWaitFor`，减少“执行了但不知是否成功”。

## 6. Android 登录场景示例（上门超人）

```yaml
agent:
  generateReport: true
  reportFileName: shangmenchaoren-login
  aiActContext: 出现权限弹窗、协议弹窗时优先点击同意

android:
  launch: 上门超人

tasks:
  - name: 登录上门超人
    flow:
      - aiAct: 如果出现登录或用户协议页面，先勾选“已阅读并同意”的圆形勾选框
      - aiInput: 手机号输入框
        value: "13188888888"
      - aiInput: 验证码输入框
        value: "123"
      - aiTap: 登录按钮
      - aiWaitFor: 已进入首页或看到登录成功后的主页面
      - aiAssert: 已登录成功
```

## 7. 实操建议

- 当元素是“图标/圆框/无文字控件”时，优先用 `aiTap` 精确描述目标位置特征。
- 当流程较复杂时，先用 `aiAct` 粗排流程，再在不稳定步骤替换成原子动作（`aiTap`/`aiInput`）。
- 报告回显直接使用 Midscene 生成的 HTML 报告，不需要自研报告渲染。

## 8. 来自 `automate-with-scripts-in-yaml` 的补充要点

### 8.1 任务级容错

每个 task 支持：
- `continueOnError: true|false`（默认 false）

示例：

```yaml
tasks:
  - name: 尝试性步骤
    continueOnError: true
    flow:
      - aiAssert: 页面存在可选入口
  - name: 后续主流程
    flow:
      - ai: 继续执行主流程
```

### 8.2 图片提示（Prompt With Images）

视觉类步骤可使用对象写法，附带 `images`：
- 常见字段：`prompt`、`images`、`convertHttpImage2Base64`
- `images` 每项包含：`name`、`url`

示例：

```yaml
tasks:
  - name: 图像辅助定位
    flow:
      - aiTap:
          locate:
            prompt: 点击和参考图一致的图标
            images:
              - name: 目标图标
                url: https://example.com/icon.png
            convertHttpImage2Base64: true
```

### 8.3 输出与日志落盘（脚本级）

在平台配置（如 `android`）中常用：
- `output`: 输出 `aiQuery/aiAssert` 结果 JSON 文件
- `unstableLogContent`: 是否输出运行日志（`true` 或文件路径）

示例：

```yaml
android:
  deviceId: emulator-5554
  output: ./result.json
  unstableLogContent: ./unstable-log.json
```

### 8.4 兼容字段提醒

- `aiAction` 是旧写法，建议新脚本统一用 `aiAct` 或 `ai`。
- `aiActionContext` 是旧字段，建议统一使用 `aiActContext`。

## 9. 详细版：`automate-with-scripts-in-yaml` 规范提炼（适合喂给其他 LLM）

### 9.1 顶层结构与平台选择

一个脚本通常由以下部分组成：
- 平台块：`web` / `android` / `ios` / `computer`（四选一或按场景使用）
- `agent`（可选）：AI 行为、报告、缓存等通用配置
- `tasks`（必填）：任务数组

最小可执行形态（Android）：

```yaml
android: {}
tasks:
  - name: smoke
    flow:
      - ai: 打开目标页面并完成一次可见交互
```

### 9.2 `agent` 推荐字段（跨平台通用）

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
    id: <string>
    strategy: read-only | read-write | write-only
```

补充说明：
- `testId` 优先级：CLI 参数 > `agent.testId` > 文件名推导。
- 新脚本建议使用 `aiActContext`，`aiActionContext` 仅兼容旧写法。

### 9.3 平台块详细字段（重点 Android）

#### Android

```yaml
android:
  deviceId: <device-id>                # 可选
  launch: <url-or-package-or-activity> # 可选
  output: <path-to-output-json>        # 可选
  unstableLogContent: <bool-or-path>   # 可选
  # 还支持 AndroidDevice 的其他参数：
  # androidAdbPath, remoteAdbHost, remoteAdbPort,
  # imeStrategy, displayId, autoDismissKeyboard,
  # keyboardDismissStrategy, screenshotResizeScale,
  # alwaysRefreshScreenInfo ...
```

#### Web（供跨平台场景参考）

常见字段：`url`、`serve`、`userAgent`、`viewportWidth`、`viewportHeight`、`cookie`、`output`、`unstableLogContent`、`forceSameTabNavigation`、`bridgeMode`、`acceptInsecureCerts`、`chromeArgs`。

#### iOS / computer

与 Android/Web 类似，按平台提供启动与设备连接相关参数；写 Android 脚本时一般不需要混用。

### 9.4 `tasks` 与 `flow` 的完整语义模板

```yaml
tasks:
  - name: <name>
    continueOnError: <boolean>
    flow:
      - ai: <prompt>
      - aiAct: <prompt>
      - aiAction: <prompt>   # 旧写法，兼容

      - aiTap: <prompt>
      - aiHover: <prompt>
      - aiInput: <prompt>
        value: <string>
      - aiKeyboardPress: <prompt>
        keyName: <string>
      - aiScroll: <prompt-or-object>
        scrollType: singleAction | scrollToBottom | scrollToTop | scrollToRight | scrollToLeft
        direction: down | up | left | right
        distance: <number-or-null>

      - aiQuery: <prompt>
        name: <string>
      - aiAssert: <prompt>
        errorMessage: <string>
        name: <string>
      - aiWaitFor: <prompt>
        timeout: <ms>

      - sleep: <ms>
      - recordToReport: <title>
        content: <description>
      - javascript: <script>
        name: <string>

      - launch: <uri-or-package>      # Android/iOS 平台动作
      - runAdbShell: <adb-shell-cmd>  # Android 平台动作
```

### 9.5 图片提示（对视觉定位很重要）

对于支持图像输入的步骤，使用对象结构：

```yaml
- aiTap:
    locate:
      prompt: 点击和参考图一致的按钮
      images:
        - name: 目标按钮
          url: https://example.com/target.png
      convertHttpImage2Base64: true
```

实践要点：
- `images[].url` 可是远程链接、本地路径、base64。
- 图片无法被模型直接访问时，设置 `convertHttpImage2Base64: true`。

### 9.6 Android 场景下的生成约束（给 LLM）

建议固定加入以下约束，以提升可执行率：
- 仅输出 YAML，不输出解释与 Markdown 代码块。
- 顶层必须包含 `android` 与 `tasks`。
- `tasks` 必须为非空数组，且每个 task 都有 `name` 和 `flow`。
- `deviceId` 未提供时不要编造；若显式提供则写入 `android.deviceId`。
- 优先 `ai`/`aiAct`，在不稳定节点使用 `aiTap`/`aiInput`/`aiKeyboardPress` 强化确定性。
- 对关键结果增加 `aiWaitFor` + `aiAssert`。
- 需要系统级动作时使用 `launch`、`runAdbShell`。

### 9.7 常见错误与规避

- 错误：输出被包在 ```yaml 代码块。  
  规避：强约束“只返回 YAML 本体”。
- 错误：根节点不是对象。  
  规避：固定模板从 `android:` 与 `tasks:` 开始。
- 错误：`tasks` 为空或漏 `flow`。  
  规避：生成后做结构校验，失败时自动重试。
- 错误：无文字控件定位不稳（如圆形同意勾选）。  
  规避：优先 `aiTap` + 位置/形状描述，必要时加图像提示。
