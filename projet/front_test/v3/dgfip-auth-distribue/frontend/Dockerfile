# syntax=docker/dockerfile:1

# ---------- Étape 1 : build -------------------------------------------
FROM node:20-alpine AS build
WORKDIR /app

COPY package.json ./
RUN npm install --no-audit --no-fund

COPY . .
# Pas de source maps (cf. vite.config.ts) : le bundle livré ne permet
# pas de reconstituer le TypeScript source depuis l'inspecteur.
RUN npm run build

# ---------- Étape 2 : service statique --------------------------------
# Image officielle "unprivileged" : tourne nativement en non-root,
# écoute sur le port 8080 (pas besoin d'être root pour un port <1024).
FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Résultat : cette image ne contient ni package.json, ni node_modules,
# ni le moindre fichier .ts/.tsx — uniquement le bundle JS/CSS minifié
# et sans source map, servi par un utilisateur non privilégié.

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q -O- http://127.0.0.1:8080/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
