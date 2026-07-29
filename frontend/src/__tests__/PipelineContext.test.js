import React from 'react';
import { render, screen, act, waitFor, fireEvent } from '@testing-library/react';
import { PipelineProvider, usePipeline } from '../contexts/PipelineContext';
// Static import, not require(): a CommonJS require bypasses Vite's transform,
// so the real module would load without import.meta.env being injected. vi.mock
// is hoisted above imports, so this still receives the mock below.
import { apiClient } from '../services/api';

vi.mock('../services/api', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
}));
vi.mock('react-hot-toast', () => ({
  __esModule: true,
  default: { success: vi.fn(), error: vi.fn() },
}));


function TestConsumer() {
  const { runs, loading, fetchRuns, startPipeline } = usePipeline();
  return (
    <div>
      <span data-testid="loading">{String(loading)}</span>
      <span data-testid="runs-count">{runs.length}</span>
      <button onClick={fetchRuns}>Fetch</button>
      <button onClick={() => startPipeline({})}>Start</button>
    </div>
  );
}

describe('PipelineContext', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test('fetchRuns loads runs from API', async () => {
    apiClient.get.mockResolvedValue({
      data: [{ run_id: 'r1', status: 'completed', timestamp: '2024-01-01' }],
    });

    render(
      <PipelineProvider>
        <TestConsumer />
      </PipelineProvider>
    );

    await act(async () => fireEvent.click(screen.getByText('Fetch')));
    await waitFor(() => expect(screen.getByTestId('runs-count')).toHaveTextContent('1'));
  });

  test('startPipeline posts and adds run', async () => {
    apiClient.post.mockResolvedValue({
      data: { run_id: 'r2', status: 'started' },
    });

    render(
      <PipelineProvider>
        <TestConsumer />
      </PipelineProvider>
    );

    await act(async () => fireEvent.click(screen.getByText('Start')));
    await waitFor(() => expect(screen.getByTestId('runs-count')).toHaveTextContent('1'));
  });
});
