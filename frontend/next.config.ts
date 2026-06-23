import type { NextConfig } from "next";

// 后端地址可通过环境变量覆盖（默认本地 FastAPI）。
// rewrites 把同源的 /api/* 代理到后端，浏览器侧无跨域 → 零改后端解决 CORS。
const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8008";

const nextConfig: NextConfig = {
  // 关闭左下角 Next dev 指示器（Route/Bundler 浮层）：dev 专属、生产本就不存在，
  // 对用户无意义。编译/运行时错误仍会照常浮出。
  devIndicators: false,

  async rewrites() {
    return [
      // 列表接口后端是带尾斜杠的 /documents/。catch-all :path* 会吃掉尾斜杠，
      // 转发成 /documents 后被 FastAPI 307 跳到后端绝对地址（浏览器跟过去即跨域失败）。
      // 故单独映射：前端调不带斜杠的路径 → 显式补上后端要求的尾斜杠，一跳到位 200。
      {
        source: "/api/v1/documents",
        destination: `${BACKEND_URL}/api/v1/documents/`,
      },
      {
        source: "/api/:path*",
        destination: `${BACKEND_URL}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
