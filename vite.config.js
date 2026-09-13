import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// GitHub Pages로 배포할 때는 base를 리포지토리 이름으로 바꾸세요.
//   예) 리포지토리가 github.com/AIF4/fullproof-dashboard 라면 base: "/fullproof-dashboard/"
export default defineConfig({
  plugins: [react()],
  base: process.env.VITE_BASE ?? "./",
  server: {
    port: 5173,
    // LIVE 모드에서 CORS 없이 백엔드(FastAPI)로 프록시합니다.
    proxy: {
      "/api": {
        target: process.env.VITE_API_TARGET ?? "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
