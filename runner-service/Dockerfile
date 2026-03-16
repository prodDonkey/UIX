FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY tsconfig.json ./
COPY src ./src

RUN npm run build

ENV RUNNER_HOST=0.0.0.0 \
    RUNNER_PORT=8100 \
    MIDSCENE_RUN_DIR=/app/midscene_run

EXPOSE 8100

CMD ["npm", "run", "start"]
