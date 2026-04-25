import React from 'react';
import { render, screen, act, waitFor, fireEvent } from '@testing-library/react';
import { PipelineProvider, usePipeline } from '../contexts/PipelineContext';

jest.mock('../services/api', () => ({
  apiClient: {
    get: jest.fn(),
    post: jest.fn(),
    delete: jest.fn(),
  },
}));
jest.mock('react-hot-toast', () => ({
  __esModule: true,
  default: { success: jest.fn(), error: jest.fn() },
}));

const { apiClient } = require('../services/api');

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
    jest.clearAllMocks();
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
