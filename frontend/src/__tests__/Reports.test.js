import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ROUTER_FUTURE } from '../routerFuture';
import Reports from '../pages/Reports';
import { usePipeline } from '../contexts/PipelineContext';
import toast from 'react-hot-toast';

vi.mock('../services/api', () => ({
  apiClient: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}));
vi.mock('../contexts/PipelineContext');
vi.mock('react-hot-toast', () => ({
  __esModule: true,
  default: {
    error: vi.fn(),
    success: vi.fn(),
  },
}));

describe('Reports page', () => {
  const mockFetchRuns = vi.fn();
  const mockGenerateReport = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    usePipeline.mockReturnValue({
      runs: [
        { run_id: 'run-1', status: 'completed', created_at: '2025-01-01' },
        { run_id: 'run-2', status: 'running', created_at: '2025-01-02' },
      ],
      fetchRuns: mockFetchRuns,
      generateReport: mockGenerateReport,
    });
  });

  test('renders Reports heading', () => {
    render(
      <MemoryRouter future={ROUTER_FUTURE}>
        <Reports />
      </MemoryRouter>
    );
    expect(
      screen.getByRole('heading', { name: /^Reports$/i })
    ).toBeInTheDocument();
  });

  test('calls fetchRuns on mount', () => {
    render(
      <MemoryRouter future={ROUTER_FUTURE}>
        <Reports />
      </MemoryRouter>
    );
    expect(mockFetchRuns).toHaveBeenCalled();
  });

  test('renders run selection dropdown when runs exist', () => {
    render(
      <MemoryRouter future={ROUTER_FUTURE}>
        <Reports />
      </MemoryRouter>
    );
    expect(screen.getByText(/select run/i)).toBeInTheDocument();
  });

  test('Generate Report button is disabled when no run selected', () => {
    render(
      <MemoryRouter future={ROUTER_FUTURE}>
        <Reports />
      </MemoryRouter>
    );
    const generateBtn = screen.getByRole('button', {
      name: /generate report/i,
    });
    expect(generateBtn).toBeDisabled();
  });
});
