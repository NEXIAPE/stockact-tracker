/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,

  // Permite el acceso en dev desde dominios proxy (GitHub Codespaces, etc.)
  allowedDevOrigins: ["*.app.github.dev", "*.githubpreview.dev"],

  experimental: {
    serverActions: {
      bodySizeLimit: "5mb", // transcripciones largas
      // Autoriza el origen reenviado por el proxy de Codespaces para que las
      // Server Actions (formularios) no se rechacen por la validación de origen.
      allowedOrigins: ["*.app.github.dev", "*.githubpreview.dev", "localhost:3000"],
    },
  },
};

module.exports = nextConfig;
