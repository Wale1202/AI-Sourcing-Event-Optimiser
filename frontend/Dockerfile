# syntax=docker/dockerfile:1.7
#
# Frontend image — multi-stage build.
#   Stage 1: build the static bundle with Vite (needs Node).
#   Stage 2: serve the bundle with nginx (no Node at runtime, ~20 MB image).
#
# VITE_API_URL is baked in at build time. The browser, not the container, makes
# API calls — so this should be the address the *browser* will use, e.g.
# http://localhost:8000 when running via docker compose on a developer machine.

FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build


FROM nginx:1.27-alpine AS runtime

# SPA-aware fallback so React Router routes resolve to index.html.
COPY nginx.conf /etc/nginx/conf.d/default.conf

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
