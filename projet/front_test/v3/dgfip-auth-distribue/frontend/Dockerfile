# syntax=docker/dockerfile:1

# ---------- Étape 1 : build -------------------------------------------
FROM node:20-alpine AS build
WORKDIR /app

# Lockfile obligatoire pour `npm ci` (builds reproductibles).
# S'il manque : lancez `npm install` en local une fois et committez
# le package-lock.json généré.
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY . .
# Pas de source maps (cf. vite.config.ts) : le bundle livré ne permet
# pas de reconstituer le TypeScript source depuis l'inspecteur.
RUN npm run build

# ---------- Étape 2 : service statique --------------------------------
# Image officielle "unprivileged" : tourne nativement en non-root
# (uid 101) et écoute sur le port 8080.
FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime

# Le contenu est lisible par l'utilisateur nginx, mais appartient à root
# et n'est donc pas modifiable à l'exécution.
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Résultat : pas de package.json, node_modules, ni .ts/.tsx — uniquement
# le bundle JS/CSS minifié, sans source map.

EXPOSE 8080

# nginx.conf DOIT contenir :
#   listen 8080;
#   location = /health { access_log off; return 200 "ok\n"; }
# (sinon try_files renvoie index.html en 200 et le check passe à tort)
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:8080/health || exit 1

CMD ["nginx", "-g", "daemon off;"]