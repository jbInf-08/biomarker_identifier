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

jest.mock('../contexts/PipelineContext', () => ({
  usePipeline: () => ({
    getRunResults: jest.fn().mockResolvedValue(null),
    getBiomarkers: jest.fn().mockResolvedValue(null),
    getRunStatus: jest.fn().mockResolvedValue(null),
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

