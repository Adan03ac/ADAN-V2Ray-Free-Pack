# ADAN NEXUS | CONNECT — frontend image
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

FROM node:22-alpine AS builder
WORKDIR /app
ARG API_PROXY_TARGET=http://backend:8000
ENV API_PROXY_TARGET=${API_PROXY_TARGET} \
    NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000
ARG API_PROXY_TARGET=http://backend:8000
ENV API_PROXY_TARGET=${API_PROXY_TARGET}

RUN addgroup -S nexus && adduser -S nexus -G nexus
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/next.config.ts ./next.config.ts
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public

USER nexus
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:3000/login || exit 1
CMD ["npx", "next", "start", "-H", "0.0.0.0", "-p", "3000"]
