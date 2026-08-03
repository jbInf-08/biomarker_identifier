import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// JSX lives in `.jsx` files. It used to sit in plain `.js` (a Create React App
// convention) with an `esbuild.loader = 'jsx'` override telling Vite to parse
// them as JSX. Vite 8 builds on Rolldown/Oxc rather than esbuild, that override
// no longer has anything to apply to, and the build failed with "JSX syntax is
// disabled". Oxc keys off the file extension and exposes no equivalent switch,
// so the files were renamed instead -- which also drops the need for any
// special configuration here.
export default defineConfig({
  plugins: [react()],

  server: {
    port: 3000,
  },

  build: {
    outDir: 'build',
    sourcemap: false,
  },

  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/setupTests.js',
    css: false,
    coverage: {
      provider: 'v8',
      reportsDirectory: './coverage',
      reporter: ['text', 'lcov'],
    },
  },
});
