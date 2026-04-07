# backend-ts

这是 Python `backend` 的 TypeScript 迁移实现。

当前状态：

- 已提供 `Fastify + Prisma + Zod` 可运行服务
- 已承接 `scripts` / `scenes` / `scene execute` 核心链路
- 默认端口 `8001`，继续与 Python `backend:8000` 并行运行
- 继续以 Python 后端作为行为对照与回退基线

## 安装

```bash
cd backend-ts
npm install
npm run prisma:generate
```

## 启动

```bash
cd backend-ts
npm run dev
```

默认端口：`8001`

## 构建

```bash
cd backend-ts
npm run build
npm run check
```

## 迁移原则

- 先保持 API 路径、请求结构、响应结构兼容，再替换内部实现
- Python `backend` 在迁移完成前仍是联调与回归基线
- 继续沿用现有 MySQL 数据库，不做破坏性 schema 变更
- 核心执行链路迁移后，必须用真实场景回放验证 `scene execute` 行为
