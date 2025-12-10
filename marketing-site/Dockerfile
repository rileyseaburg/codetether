# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies (using install for compatibility)
RUN npm install --legacy-peer-deps

# Copy source code
COPY . .

# Create public directory if it doesn't exist
RUN mkdir -p public

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

# Build the Next.js application
RUN npm run build

# Production stage
FROM node:20-alpine AS runner

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
