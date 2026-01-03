# Build stage
FROM node:20-slim AS builder

WORKDIR /app

# Copy all source code first
COPY . .

# Create public directory if it doesn't exist
RUN mkdir -p public

# Clean install all dependencies
RUN rm -rf node_modules package-lock.json && npm install

# Set build-time environment variables for NextAuth
ARG AUTH_SECRET
ARG KEYCLOAK_CLIENT_ID=a2a-monitor
ARG KEYCLOAK_CLIENT_SECRET
ARG KEYCLOAK_ISSUER=https://auth.quantum-forge.io/realms/quantum-forge
ARG NEXTAUTH_URL=https://a2a.quantum-forge.net

ENV AUTH_SECRET=$AUTH_SECRET
ENV KEYCLOAK_CLIENT_ID=$KEYCLOAK_CLIENT_ID
ENV KEYCLOAK_CLIENT_SECRET=$KEYCLOAK_CLIENT_SECRET
ENV KEYCLOAK_ISSUER=$KEYCLOAK_ISSUER
ENV NEXTAUTH_URL=$NEXTAUTH_URL

# Build the Next.js application using node_modules/.bin directly
RUN ./node_modules/.bin/next build

# Production stage
FROM node:20-slim AS runner

WORKDIR /app

ENV NODE_ENV=production
ENV PORT=3000

# Auth configuration - these will be set at runtime via Kubernetes
ENV NEXTAUTH_URL=https://a2a.quantum-forge.net
ENV KEYCLOAK_ISSUER=https://auth.quantum-forge.io/realms/quantum-forge
ENV KEYCLOAK_CLIENT_ID=a2a-monitor
# Runtime secrets - baked in for standalone build (use K8s secrets in production for better security)
ENV AUTH_SECRET=Gzez2UkA76TcFpnUEXUmT16+/G3UX2RmoGxyByfAJO4=
ENV KEYCLOAK_CLIENT_SECRET=Boog6oMQhr6dlF5tebfQ2FuLMhAOU4i1

# Create non-root user
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Copy built application (public may be empty)
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

CMD ["node", "server.js"]
