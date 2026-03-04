# API 文档（M4 交付版）

## 基础信息
- Base URL: `http://127.0.0.1:8000`
- Content-Type: `application/json`

## 健康检查
### GET /health
- 说明: 服务健康检查
- 响应示例:
```json
{"status":"ok"}
```

## 脚本接口
### GET /api/scripts
- 说明: 获取脚本列表（按更新时间倒序）

### GET /api/scripts/{id}
- 说明: 获取脚本详情

### POST /api/scripts
- 说明: 创建脚本
- 请求示例:
```json
{
  "name": "demo-script",
  "content": "android:\n  deviceId: \"abc\"\n\ntasks:\n  - name: demo\n    flow:\n      - aiAction: open Settings app\n",
  "source_type": "manual"
}
```

### PUT /api/scripts/{id}
- 说明: 更新脚本（会自动生成版本快照）

### DELETE /api/scripts/{id}
- 说明: 删除脚本

### POST /api/scripts/{id}/copy
- 说明: 复制脚本

### POST /api/scripts/{id}/validate
- 说明: YAML 校验
- 请求:
```json
{"content":"android: {}\n\ntasks:\n- name: demo\n  flow:\n  - aiAction: open Settings app\n"}
```
- 响应:
```json
{"valid":true,"line":null,"column":null,"message":null}
```

### POST /api/scripts/generate
- 说明: 自然语言生成 YAML
- 请求:
```json
{
  "prompt": "打开高德地图查看深圳北的地铁",
  "device_id": "5bce0b36",
  "language": "zh",
  "model": "qwen-plus"
}
```
- 成功响应:
```json
{
  "yaml": "android:\n  deviceId: \"5bce0b36\"\n\ntasks:\n  - name: ...",
  "warnings": []
}
```

## 运行接口
### GET /api/runs?script_id={id}
- 说明: 获取运行记录（可按脚本过滤）

### POST /api/runs
- 说明: 发起执行
- 请求:
```json
{"script_id": 1}
```

### GET /api/runs/{id}
- 说明: 获取运行详情（状态/耗时/错误等）

### GET /api/runs/{id}/logs
- 说明: 获取运行日志
- 响应:
```json
{"content":"..."}
```

### POST /api/runs/{id}/cancel
- 说明: 取消执行（终止整个进程组）

### GET /api/runs/{id}/report
- 说明: 获取报告元数据
- 响应:
```json
{
  "report_path": "/abs/path/report.html",
  "preview_url": "http://127.0.0.1:8000/api/runs/12/report/file",
  "download_url": "http://127.0.0.1:8000/api/runs/12/report/file?download=1"
}
```

### GET /api/runs/{id}/report/file
- 说明: 预览报告文件（inline）

### GET /api/runs/{id}/report/file?download=1
- 说明: 下载报告文件（attachment）

## 状态机说明
- `queued` -> `running` -> `success | failed | cancelled`

## 错误码约定
- `404`: 资源不存在（script/run/report）
- `422`: 生成结果校验失败（YAML 结构不合法）
- `400`: 生成失败（模型调用异常/配置异常）
- `403`: 报告路径越权访问
