import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ROUTER_FUTURE } from '../routerFuture';

jest.mock('../services/api', () => ({
  apiClient: {
    get: jest.fn().mockResolvedValue({
      data: { available: false, message: 'OK' },
    }),
    post: jest.fn().mockResolvedValue({ data: {} }),
    interceptors: {
      request: { use: jest.fn() },
      response: { use: jest.fn() },
    },
  },
  api: {},
}));

jest.mock('react-hot-toast', () => ({
  __esModule: true,
  default: {
    error: jest.fn(),
    success: jest.fn(),
  },
}));

// These must be stable across renders. Results.js wraps loadResults in a
// useCallback keyed on these functions and calls it from a useEffect, so
// returning fresh jest.fn()s from usePipeline() on every render changed the
// dep identities each pass, re-fired the effect, and re-entered setLoading(true)
// forever -- the component never left its spinner and no heading ever rendered.
const mockGetRunResults = jest.fn().mockResolvedValue(null);
const mockGetBiomarkers = jest.fn().mockResolvedValue(null);
const mockGetRunStatus = jest.fn().mockResolvedValue(null);
const mockGenerateReport = jest.fn().mockResolvedValue(null);

jest.mock('../contexts/PipelineContext', () => ({
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

