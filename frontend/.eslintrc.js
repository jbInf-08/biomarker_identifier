/**
 * Replaces the `react-app` / `react-app/jest` presets, which shipped inside
 * react-scripts and disappeared with it when the build moved to Vite.
 */
module.exports = {
  root: true,
  env: {
    browser: true,
    es2022: true,
    node: true,
  },
  parserOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module',
    ecmaFeatures: { jsx: true },
  },
  settings: {
    react: { version: 'detect' },
  },
  plugins: ['react', 'react-hooks', 'jsx-a11y'],
  extends: [
    'eslint:recommended',
    'plugin:react/recommended',
    'plugin:react-hooks/recommended',
    'plugin:jsx-a11y/recommended',
  ],
  rules: {
    // This codebase does not use prop-types.
    'react/prop-types': 'off',

    // Deliberately NOT extending plugin:react/jsx-runtime. The source still
    // uses classic `import React from 'react'`; with the jsx-runtime preset
    // those imports are reported as unused. Keeping the classic config lets
    // react/jsx-uses-react mark them as used. (Vite's React plugin uses the
    // automatic runtime regardless, so the imports are merely redundant.)

    // Pre-existing findings that the react-app preset did not treat as errors.
    // Left visible as warnings rather than silently disabled -- and rather than
    // failing the build on debt this migration did not introduce. Accessibility
    // is separately gated for real by the Lighthouse CI job.
    'jsx-a11y/label-has-associated-control': 'warn',
    'jsx-a11y/no-static-element-interactions': 'warn',
    'jsx-a11y/click-events-have-key-events': 'warn',
    'no-case-declarations': 'warn',
    'no-prototype-builtins': 'warn',

    // react-app set this to 'warn', and the tree carries ~23 unused imports and
    // locals as a result. Kept at 'warn' so the migration matches the previous
    // strictness exactly instead of failing on pre-existing dead code; worth a
    // separate cleanup pass.
    'no-unused-vars': ['warn', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
  },
  overrides: [
    {
      // Vitest globals (vite.config.js sets test.globals = true).
      files: ['src/**/*.test.js', 'src/setupTests.js'],
      globals: {
        describe: 'readonly',
        it: 'readonly',
        test: 'readonly',
        expect: 'readonly',
        vi: 'readonly',
        beforeEach: 'readonly',
        afterEach: 'readonly',
        beforeAll: 'readonly',
        afterAll: 'readonly',
      },
    },
  ],
};
