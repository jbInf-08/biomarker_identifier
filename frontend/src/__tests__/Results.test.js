import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ROUTER_FUTURE } from '../routerFuture';

vi.mock('../services/api', () => ({
  apiClient: {
    get: vi.fn().mockResolvedValue({
      data: { available: false, message: 'OK' },
    }),
    post: vi.fn().mockResolvedValue({ data: {} }),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  },
  api: {},
}));

vi.mock('react-hot-toast', () => ({
  __esModule: true,
  default: {
    error: vi.fn(),
    success: vi.fn(),
  },
}));

// These must be stable across renders. Results.js wraps loadResults in a
// useCallback keyed on these functions and calls it from a useEffect, so
// returning fresh vi.fn()s from usePipeline() on every render changed the
// dep identities each pass, re-fired the effect, and re-entered setLoading(true)
// forever -- the component never left its spinner and no heading ever rendered.
const mockGetRunResults = vi.fn().mockResolvedValue(null);
const mockGetBiomarkers = vi.fn().mockResolvedValue(null);
const mockGetRunStatus = vi.fn().mockResolvedValue(null);
const mockGenerateReport = vi.fn().mockResolvedValue(null);

vi.mock('../contexts/PipelineContext', () => ({
  usePipeline: () => ({
    getRunResults: mockGetRunResults,
    getBiomarkers: mockGetBiomarkers,
    getRunStatus: mockGetRunStatus,
    generateReport: mockGenerateReport,
  }),
}));

import Results from '../pages/Results';

describe('Results page', () => {
  test('renders results view (heading or empty state)', async () => {
    render(
      <MemoryRouter future={ROUTER_FUTURE} initialEntries={['/results/test-run']}>
        <Routes>
          <Route path="results/:runId" element={<Results />} />
        </Routes>
      </MemoryRouter>
    );

    // After async load, component shows either "Analysis Results" (with data) or "No results found" (mock returns null)
    const heading = await screen.findByRole('heading', { name: /analysis results|no results found/i });
    expect(heading).toBeInTheDocument();
  });
});

