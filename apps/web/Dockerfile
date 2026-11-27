# ArchAI Studio. NEXT_PUBLIC_* values are inlined at build time, so the API URL is a build argument.
FROM node:22-alpine AS deps
WORKDIR /opt/archai
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci

FROM node:22-alpine AS build
WORKDIR /opt/archai
ARG NEXT_PUBLIC_ARCHAI_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_ARCHAI_API_URL=${NEXT_PUBLIC_ARCHAI_API_URL} \
    NEXT_TELEMETRY_DISABLED=1 \
    NEXT_OUTPUT=standalone
COPY --from=deps /opt/archai/node_modules ./node_modules
COPY apps/web ./
RUN npm run build

FROM node:22-alpine
WORKDIR /opt/archai
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
COPY --from=build --chown=node:node /opt/archai/.next/standalone ./
COPY --from=build --chown=node:node /opt/archai/.next/static ./.next/static
USER node
EXPOSE 3000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD ["wget", "-q", "-O", "/dev/null", "http://127.0.0.1:3000/"]
CMD ["node", "server.js"]
