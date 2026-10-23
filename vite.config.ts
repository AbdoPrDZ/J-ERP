import { fileURLToPath, URL } from 'node:url';
import fs from 'node:fs';
import path from 'node:path';

import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// @ts-expect-error - plain JS dev plugin (no type declarations)
import jerpDev from './tools/vite-plugin-jerp.mjs';

const projectRoot = fileURLToPath(new URL('.', import.meta.url));
const uiSrc = fileURLToPath(new URL('./jerp/ui/src', import.meta.url));
const modules = fileURLToPath(new URL('./modules', import.meta.url));
const outDir = fileURLToPath(new URL('./data/ui', import.meta.url));

// Use the app port from jerp.config.json so the dev proxies match the backend.
const jerpConfig = JSON.parse(
  fs.readFileSync(fileURLToPath(new URL('./jerp.config.json', import.meta.url)), 'utf8'),
);
const backend = `http://127.0.0.1:${jerpConfig?.app?.port ?? 1347}`;

export default defineConfig(({ command }) => ({
  // In dev the project root is the Vite root, so the HTML entry at public/
  // can reach ../jerp/ui/src. For builds, public/ becomes the root so the
  // emitted index.html lands directly in data/ui.
  root: command === 'build' ? 'public' : '.',
  publicDir: false,

  plugins: [
    react(),
    tailwindcss(),
    jerpDev('modules'),
    {
      name: 'jerp-dev-entry',
      configureServer(server) {
        server.middlewares.use(async (req, res, next) => {
          const url = req.url || '/';
          const pathname = decodeURIComponent(url.split('?')[0]);
          const acceptsHtml = (req.headers.accept || '').includes('text/html');

          // The favicon lives in public/; in dev the Vite root is the project
          // root, so map the conventional URL to the static file.
          if (pathname === '/favicon.ico') {
            req.url = '/public/favicon.ico';
            return next();
          }

          if (!acceptsHtml) {
            return next();
          }

          // The app root needs the server's redirect logic (login / home /
          // database manager), so let the backend decide.
          if (pathname === '/') {
            try {
              const response = await fetch(`${backend}/`, {
                redirect: 'manual',
                headers: { accept: 'text/html', cookie: req.headers.cookie || '' },
              });
              const location = response.headers.get('location');
              if (location) {
                res.statusCode = response.status;
                const setCookie = response.headers.get('set-cookie');
                if (setCookie) {
                  res.setHeader('set-cookie', setCookie);
                }
                res.setHeader('location', location);
                res.end();
                return;
              }
            } catch {
              // backend down -> serve the shell
            }
          }

          // Serve the shell for HTML navigations that are not real files.
          const skip =
            pathname.startsWith('/@') ||
            pathname.startsWith('/node_modules') ||
            pathname.startsWith('/public/');
          let exists = false;
          try {
            exists = fs.statSync(path.join(projectRoot, pathname)).isFile();
          } catch {
            exists = false;
          }
          if (!skip && (pathname === '/' || !exists)) {
            req.url = '/public/index.html';
          }
          next();
        });
      },
    },
  ],

  resolve: {
    alias: {
      '@': uiSrc,
      '@jerp/ui': fileURLToPath(new URL('./jerp/ui/src/core/runtime.ts', import.meta.url)),
      '@modules': modules,
    },
  },

  server: {
    port: 5173,
    // Proxies are collected from the backend by the jerpDev plugin
    // (see tools/vite-plugin-jerp.mjs -> GET /__endpoints).
    fs: {
      allow: [projectRoot],
    },
  },

  build: {
    outDir,
    emptyOutDir: true,
    manifest: true,
    sourcemap: true,
    rollupOptions: {
      // React is provided at runtime by react-runtime.js via the import map.
      external: ['react', 'react-dom', 'react-dom/client', 'react/jsx-runtime'],
      // Keep the runtime entry's exports (it is a library-style entry, not an app).
      preserveEntrySignatures: 'strict',
      input: {
        index: fileURLToPath(new URL('./public/index.html', import.meta.url)),
        // Shared runtime: React + the J-ERP UI kit, exposed at a stable URL for
        // module view bundles via the import map.
        runtime: fileURLToPath(new URL('./jerp/ui/src/core/runtime.ts', import.meta.url)),
      },
      output: {
        entryFileNames: (chunk) =>
          chunk.name === 'runtime' ? 'runtime.js' : 'assets/[name]-[hash].js',
        chunkFileNames: 'assets/[name]-[hash].js',
        assetFileNames: 'assets/[name]-[hash][extname]',
      },
    },
  },
}));
