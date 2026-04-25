import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ROUTER_FUTURE } from '../routerFuture';
import Reports from '../pages/Reports';
import { usePipeline } from '../contexts/PipelineContext';
import toast from 'react-hot-toast';

jest.mock('../services/api', () => ({
  apiClient: { get: jest.fn(), post: jest.fn(), delete: jest.fn() },
}));
jest.mock('../contexts/PipelineContext');
jest.mock('react-hot-toast', () => ({
  __esModule: true,
  default: {
    error: jest.fn(),
    success: jest.fn(),
  },
}));

describe('Reports page', () => {
  const mockFetchRuns = jest.fn();
  const mockGenerateReport = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
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
