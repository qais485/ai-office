FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:alpine AS runtime

# Origin of the backend API for the nginx proxy below. The official nginx image
# renders /etc/nginx/templates/*.template with envsubst at container start, so
# this can be overridden per environment (e.g. docker-compose sets
# BACKEND_URL=http://backend:8000). No provider URL is hardcoded here.
ENV BACKEND_URL=http://localhost:8000

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:80/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
