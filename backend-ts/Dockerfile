# syntax=docker/dockerfile:1

# ---- build stage ----
FROM node:20-bookworm-slim AS build
WORKDIR /app

# 依赖安装(利用缓存:先只拷贝清单)
COPY package.json package-lock.json ./
RUN npm ci

# 生成 Prisma Client(运行时需要 .prisma/client)
COPY prisma ./prisma
RUN npx prisma generate

# 编译 TypeScript -> dist
COPY tsconfig.json ./
COPY src ./src
RUN npm run build

# 移除 devDependencies,仅保留运行期依赖(Prisma 生成产物保留在 node_modules/.prisma)
RUN npm prune --omit=dev

# ---- runtime stage ----
FROM node:20-bookworm-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production

# @midscene/android 通过 adb 连接网络真机,需要 adb 客户端
RUN apt-get update \
 && apt-get install -y --no-install-recommends android-tools-adb \
 && rm -rf /var/lib/apt/lists/*

COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/dist ./dist
COPY --from=build /app/prisma ./prisma
COPY package.json ./

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 8001
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["node", "dist/index.js"]
