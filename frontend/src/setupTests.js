// jest-dom adds custom matchers for DOM assertions (e.g. toBeInTheDocument).
// Version 6+ ships a dedicated Vitest entry that registers them on Vitest's
// expect rather than Jest's.
import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

import './i18n';

// react-scripts' Jest preset unmounted rendered trees between tests
// automatically; Vitest does not, so do it explicitly to keep tests isolated.
afterEach(() => {
  cleanup();
});
