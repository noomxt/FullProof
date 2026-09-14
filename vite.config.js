import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 상대 자산 경로를 사용해 GitHub Pages의 저장소 하위 경로에서도 실행합니다.
export default defineConfig({
  plugins: [react()],
  base: process.env.VITE_BASE ?? "./",
  server: {
    port: 5173,
    // 선택 실행한 로컬 규칙 시연 API로 개발 요청을 전달합니다.
    proxy: {
      "/api": {
        target: process.env.VITE_API_TARGET ?? "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
