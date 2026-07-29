const js = require('@eslint/js');
const globals = require('globals');
const react = require('eslint-plugin-react');
const reactHooks = require('eslint-plugin-react-hooks');
const jsxA11y = require('eslint-plugin-jsx-a11y');

/**
 * ESLint 9 flat config. Replaces the .eslintrc.js added when the build moved
 * off Create React App, which in turn replaced the `react-app` presets that
 * used to ship inside react-scripts.
 */
module.exports = [
  {
    ignores: ['build/**', 'coverage/**', 'node_modules/**', 'public/**'],
  },

  js.configs.recommended,

  {
    files: ['**/*.{js,jsx}'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: {
        ...globals.browser,
        ...globals.node,
      },
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
    },
    settings: {
      react: { version: 'detect' },
    },
    plugins: {
      react,
      'react-hooks': reactHooks,
      'jsx-a11y': jsxA11y,
    },
    rules: {
      ...react.configs.recommended.rules,
      ...reactHooks.configs.recommended.rules,
      ...jsxA11y.configs.recommended.rules,

      // This codebase does not use prop-types.
      'react/prop-types': 'off',

      // react/jsx-runtime is deliberately not applied: the source uses classic
      // `import React from 'react'`, and react/jsx-uses-react (part of the
      // recommended set above) is what marks those imports as used. Vite's
      // React plugin uses the automatic runtime regardless, so the imports are
      // merely redundant rather than wrong.

      // Pre-existing findings that the react-app preset also reported as
      // warnings. Kept at 'warn' so this config matches the previous
      // strictness rather than failing the build on debt it did not create.
      // Accessibility is separately gated for real by the Lighthouse CI job.
      'no-unused-vars': ['warn', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
      'jsx-a11y/label-has-associated-control': 'warn',
      'jsx-a11y/no-static-element-interactions': 'warn',
      'jsx-a11y/click-events-have-key-events': 'warn',
      'no-case-declarations': 'warn',
      'no-prototype-builtins': 'warn',
    },
  },

  {
    // Vitest globals (vite.config.js sets test.globals = true).
    files: ['src/**/*.test.js', 'src/setupTests.js'],
    languageOptions: {
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
  },

  {
    // Config files run in Node.
    files: ['*.config.js', '.lighthouserc.js', 'lighthouserc.js'],
    languageOptions: {
      sourceType: 'commonjs',
      globals: { ...globals.node },
    },
  },
];
