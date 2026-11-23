FROM node:22-alpine AS build

WORKDIR /src

RUN corepack enable && corepack prepare pnpm@9.12.3 --activate

COPY web/package.json web/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY web/ ./

ARG VITE_API_BASE=
ENV VITE_API_BASE=$VITE_API_BASE

RUN pnpm build

FROM caddy:2-alpine

COPY infra/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /src/dist /srv/web
