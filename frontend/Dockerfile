FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:1.27-alpine

RUN apk add --no-cache gettext

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY docker-entrypoint.sh /docker-entrypoint.sh
COPY public/app-config.template.js /usr/share/nginx/html/app-config.template.js
COPY --from=build /app/dist /usr/share/nginx/html

RUN chmod +x /docker-entrypoint.sh

ENV API_BASE_URL=/api \
    ANDROID_PLAYGROUND_URL=http://localhost:5800

EXPOSE 80

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
