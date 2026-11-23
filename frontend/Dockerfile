# syntax=docker/dockerfile:1
FROM node:22.23.5-alpine3.24 AS build
WORKDIR /app
RUN --mount=type=bind,source=package.json,target=package.json \
    --mount=type=bind,source=package-lock.json,target=package-lock.json \
    --mount=type=cache,target=/root/.npm \
    npm ci --strict-peer-deps
COPY . .
ARG VITE_CURRENCY
RUN npm run build

FROM nginx:1.30.7-alpine3.24 AS runtime
WORKDIR /usr/share/nginx/html
COPY --link nginx.conf /etc/nginx/nginx.conf
COPY --link --from=build /app/dist/ ./
USER 101:101
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s \
    CMD wget --quiet --spider http://127.0.0.1:8080/healthz || exit 1
ENTRYPOINT ["nginx", "-g", "daemon off;"]
