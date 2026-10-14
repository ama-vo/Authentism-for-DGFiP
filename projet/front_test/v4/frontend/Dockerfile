# syntax=docker/dockerfile:1

# ---------- Étape 1 : build (vérification TypeScript + bundle Vite) ------
FROM node:20-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY index.html tsconfig.json vite.config.ts ./
COPY src ./src
# `npm run build` = `tsc -b && vite build` : échoue si le typage est faux.
# (Correction du bug v3 : le Dockerfile lançait `npm run dev`.)
RUN npm run build

# ---------- Étape 2 : service statique, non-root -------------------------
FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY proxy_webapp.inc /etc/nginx/conf.d/proxy_webapp.inc

# L'image ne contient que le bundle minifié, sans sources ni source maps.
EXPOSE 8080 8443

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
    CMD wget -q -O /dev/null http://127.0.0.1:8080/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
