import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { ROUTER_FUTURE } from '../routerFuture';
import ClinicalAnnotation from '../pages/ClinicalAnnotation';
import { usePipeline } from '../contexts/PipelineContext';
import { apiClient } from '../services/api';
import toast from 'react-hot-toast';

jest.mock('../contexts/PipelineContext');
jest.mock('../services/api', () => ({
  apiClient: {
    get: jest.fn(),
    post: jest.fn(),
    delete: jest.fn(),
  },
}));
jest.mock('react-hot-toast', () => ({
  __esModule: true,
  default: {
    error: jest.fn(),
  },
}));

describe('ClinicalAnnotation page', () => {
  const mockFetchRuns = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    usePipeline.mockReturnValue({
      runs: [],
      fetchRuns: mockFetchRuns,
    });
  });

  test('renders no run selected message when no runId', () => {
    render(
      <MemoryRouter future={ROUTER_FUTURE} initialEntries={['/clinical']}>
        <Routes>
          <Route path="/clinical" element={<ClinicalAnnotation />} />
        </Routes>
      </MemoryRouter>
    );
    expect(
      screen.getByText(/choose a completed analysis run to view clinical annotations/i)
    ).toBeInTheDocument();
  });

  test('renders loading then annotations when runId provided', async () => {
    apiClient.post.mockResolvedValue({
      data: {
        annotation_summary: {
          total_biomarkers: 1,
          high_relevance_count: 1,
        },
        annotated_biomarkers: [
          {
            gene_symbol: 'TP53',
            p_value: 0.001,
            fold_change: 2.0,
            clinical_summary: {
              clinical_relevance_score: 0.8,
              is_cancer_gene: true,
              has_therapeutic_implications: false,
            },
          },
        ],
      },
    });

    render(
      <MemoryRouter future={ROUTER_FUTURE} initialEntries={['/clinical/run-123']}>
        <Routes>
          <Route path="/clinical/:runId?" element={<ClinicalAnnotation />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith(
        expect.stringContaining('/clinical/annotate-run/run-123')
      );
    });

    await waitFor(() => {
      expect(screen.getByText('TP53')).toBeInTheDocument();
    });
  });

  test('shows toast error when API fails', async () => {
    apiClient.post.mockRejectedValue(new Error('Network error'));

    render(
      <MemoryRouter future={ROUTER_FUTURE} initialEntries={['/clinical/run-123']}>
        <Routes>
          <Route path="/clinical/:runId?" element={<ClinicalAnnotation />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        'Failed to load clinical annotations'
      );
    });
  });
});
