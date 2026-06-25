# syntax=docker/dockerfile:1

# ---- build stage ----
FROM node:20-alpine AS build
WORKDIR /app
RUN corepack enable

# 依赖安装(利用缓存)
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# 构建静态产物 -> dist
# 说明:API_BASE_URL 不在构建期写死,改为运行时通过 app-config.js 注入
COPY . .
RUN pnpm build

# ---- runtime stage ----
FROM nginx:1.27-alpine AS runtime

# 静态产物
COPY --from=build /app/dist /usr/share/nginx/html

# 运行时配置模板(由 entrypoint 用 envsubst 生成 app-config.js)
COPY public/app-config.template.js /usr/share/nginx/html/app-config.template.js

# nginx 配置模板:nginx 官方镜像会自动用环境变量渲染 /etc/nginx/templates/*.template
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# 仅替换我们关心的变量,避免误伤 nginx 自身的 $uri/$host 等
ENV NGINX_ENVSUBST_FILTER="BACKEND_UPSTREAM"

# 生成运行时 app-config.js(放入官方镜像的启动钩子目录,nginx 启动前执行)
COPY docker-entrypoint.sh /docker-entrypoint.d/40-app-config.sh
RUN chmod +x /docker-entrypoint.d/40-app-config.sh

EXPOSE 80
