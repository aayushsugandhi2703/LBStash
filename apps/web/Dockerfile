# syntax=docker/dockerfile:1.7-labs
# Web image: the Next.js standalone server on Node (the Python base image has no Node). Build context: apps/web.
FROM node:24-alpine AS build
ARG GATEWAY_URL=http://gateway:3000
ENV NEXT_TELEMETRY_DISABLED=1 GATEWAY_URL=${GATEWAY_URL}
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund
COPY . .
RUN NODE_ENV=production npx next build

FROM node:24-alpine AS run
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
WORKDIR /app
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
COPY --from=build --chown=node:node /app/public ./public
USER node
EXPOSE 3000
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 CMD wget -qO- http://127.0.0.1:3000/ >/dev/null || exit 1
CMD ["node", "server.js"]
