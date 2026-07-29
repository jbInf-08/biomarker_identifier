import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ROUTER_FUTURE } from '../routerFuture';

// Minimal mock for PipelineContext
vi.mock('../contexts/PipelineContext', () => ({
  usePipeline: () => ({
    runs: [],
    loading: false,
    fetchRuns: vi.fn(),
  }),
}));
vi.mock('../services/api', () => ({
  api: {
    pipeline: {
      getRunAnalyticsDashboard: vi.fn(() => Promise.reject(new Error('no data'))),
    },
  },
}));

import Dashboard from '../pages/Dashboard';

function renderDashboard() {
  return render(
    <MemoryRouter future={ROUTER_FUTURE}>
      <Dashboard />
    </MemoryRouter>
  );
}

describe('Dashboard page', () => {
  test('renders dashboard heading and quick actions', () => {
    renderDashboard();

    expect(
      screen.getAllByRole('heading', { name: /dashboard/i }).length
    ).toBeGreaterThan(0);

    const uploadLinks = screen.getAllByRole('link', { name: /upload data/i });
    expect(uploadLinks.length).toBeGreaterThanOrEqual(1);
  });
});

