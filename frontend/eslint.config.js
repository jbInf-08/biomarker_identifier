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

      // These three are at zero findings, so they stay at the recommended
      // 'error' severity to keep them there. no-case-declarations and
      // no-prototype-builtins take their severity from js.configs.recommended
      // above and need no entry here.
      'no-unused-vars': [
        'error',
        {
          argsIgnorePattern: '^_',
          varsIgnorePattern: '^_',
          // ESLint 9's recommended set turns on caughtErrors: 'all', which
          // ESLint 8 did not. Deliberately-ignored catch bindings are named _
          // in this codebase, so honour the same convention for them.
          caughtErrorsIgnorePattern: '^_',
        },
      ],

      // At zero, so they hold at the recommended error severity. The forms
      // were checked in a browser after the change, not just against the rule:
      // every label focuses its control on click, and the menu backdrop is
      // reachable and activatable from the keyboard.
      'jsx-a11y/label-has-associated-control': 'error',
      'jsx-a11y/no-static-element-interactions': 'error',
      'jsx-a11y/click-events-have-key-events': 'error',
    },
  },

  {
    // Vitest globals (vite.config.mjs sets test.globals = true).
    // Both extensions: the tests carrying JSX are .test.jsx since the JSX-in-.js
    // files were renamed for Vite 8, and managedLifecycle.test.js has none.
    files: ['src/**/*.test.{js,jsx}', 'src/setupTests.js'],
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
    // Config files run in Node. Only this file is CommonJS -- lighthouserc.js
    // is ESM, and the previous `*.config.js` glob also caught vite.config.js,
    // forcing sourceType 'commonjs' onto files that use `import`. That made
    // vite.config.js an unconditional parse error, invisible because the `lint`
    // script only covers src/. It is now vite.config.mjs and neither needs an
    // entry here: .mjs parses as a module by definition, and the
    // `**/*.{js,jsx}` block above covers lighthouserc.js with the Node globals.
    files: ['eslint.config.js'],
    languageOptions: {
      sourceType: 'commonjs',
      globals: { ...globals.node },
    },
  },
];
