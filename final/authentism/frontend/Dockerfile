# ---- Étape 1 : compilation de l'application React ----
FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# ---- Étape 2 : nginx sert le site et fait passerelle vers l'API ----
FROM nginx:stable-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY proxy_api.conf /etc/nginx/proxy_api.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80 443
