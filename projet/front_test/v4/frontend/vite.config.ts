import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// En développement, /api est relayé vers webapp (même origine : les
// cookies de session fonctionnent sans CORS). En production, c'est
// Nginx qui fait ce relais (voir nginx.conf).
const target = process.env.VITE_API_TARGET ?? "http://127.0.0.1:5000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target, changeOrigin: false, secure: false, rewrite: (p) => p.replace(/^\/api/, "") },
    },
  },
  build: {
    // Pas de source maps : le TypeScript d'origine n'est pas
    // reconstructible depuis l'inspecteur du navigateur.
    sourcemap: false,
    minify: "esbuild",
  },
  esbuild: { drop: ["console", "debugger"] },
});
