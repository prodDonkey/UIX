# 部署与运维手册（M4 交付版）

## 1. 环境要求
- Node.js >= 18
- Python >= 3.11
- `uv` 已安装

## 2. 后端部署
```bash
cd /Users/yaohongliang/work/liuyao/AI/UI/ui_demo/backend
uv sync
cp .env.example .env
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 3. 前端部署（开发）
```bash
cd /Users/yaohongliang/work/liuyao/AI/UI/ui_demo/frontend
npm install
npm run dev -- --port 5173
```

## 4. 前端构建（生产）
```bash
cd /Users/yaohongliang/work/liuyao/AI/UI/ui_demo/frontend
npm run build
```

## 5. 关键环境变量
### 执行 Midscene
- `MIDSCENE_MODEL_BASE_URL`
- `MIDSCENE_MODEL_API_KEY`
- `MIDSCENE_MODEL_NAME`
- `MIDSCENE_MODEL_FAMILY`

### 生成 YAML（优先）
- `LLM_BASE_URL`
- `LLM_API_KEY`
- `LLM_MODEL_NAME`
- 未配 `LLM_*` 时回退 `MIDSCENE_*`

### 运行目录
- `RUN_SCRIPTS_DIR`（临时脚本目录）
- `RUN_LOGS_DIR`（日志目录）
- `REPORT_ROOT_DIR`（报告根目录白名单）

## 6. 运维巡检
- 检查后端健康：`curl http://127.0.0.1:8000/health`
- 检查前端可访问：`http://127.0.0.1:5173`
- 检查 adb 设备：`adb devices -l`

## 7. 常见问题
1. 生成失败提示模型未配置
- 检查 `.env` 中 `LLM_*` 或 `MIDSCENE_*`
- 重启后端服务

2. 点击取消后仍执行
- 已实现进程组终止，若仍发生，排查外部 adb 进程是否由其他任务启动

3. 报告无法预览
- 确认报告文件在 `REPORT_ROOT_DIR` 范围内

## 8. 安全建议
- API Key 不要提交到仓库
- 发现泄露后立即旋转 key
