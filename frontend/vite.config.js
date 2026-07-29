import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// This project keeps JSX in plain `.js` files (a Create React App convention).
// esbuild only treats `.jsx` as JSX by default, so both the dev/build pipeline
// and the dependency pre-bundler are told to parse `src/**/*.js` as JSX.
export default defineConfig({
  plugins: [react({ include: /\.(js|jsx)$/ })],

  esbuild: {
    loader: 'jsx',
    include: /src\/.*\.jsx?$/,
    exclude: [],
  },

  optimizeDeps: {
    esbuildOptions: {
      loader: { '.js': 'jsx' },
    },
  },

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
