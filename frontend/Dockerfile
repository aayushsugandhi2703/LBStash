# syntax=docker/dockerfile:1.7-labs
# Web image: the Next.js standalone server on Node (the Python base image has no Node). Build context: frontend.
FROM node:24-alpine AS build
ARG GATEWAY_URL=http://gateway:3000
ENV NEXT_TELEMETRY_DISABLED=1 GATEWAY_URL=${GATEWAY_URL}
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund
COPY . .
RUN NODE_ENV=production npx next build
# Image Optimization is off (next.config.mjs) and nothing uses next/image, so drop the sharp/libvips binaries Next still traces.
RUN rm -rf .next/standalone/node_modules/@img .next/standalone/node_modules/sharp

# Only `node server.js` runs here: remove npm, corepack, yarn and the node headers from the stock image, then flatten into
# `scratch` so the deletions really shrink the image.
FROM node:24-alpine AS rootfs
RUN rm -rf /usr/local/lib/node_modules /usr/local/bin/npm /usr/local/bin/npx /usr/local/bin/corepack \
           /usr/local/bin/yarn /usr/local/bin/yarnpkg /opt/yarn-v1.22.22 /usr/local/include/node /var/cache/*

FROM scratch AS run
COPY --from=rootfs / /
# scratch drops the image config, so repeat what node:24-alpine set (PATH, user, workdir).
ENV PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
WORKDIR /app
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
COPY --from=build --chown=node:node /app/public ./public
USER node
EXPOSE 3000
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 CMD wget -qO- http://127.0.0.1:3000/ >/dev/null || exit 1
CMD ["node", "server.js"]
