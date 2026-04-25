import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ROUTER_FUTURE } from '../routerFuture';

// Mock contexts used by DataUpload
jest.mock('../contexts/PipelineContext', () => ({
  usePipeline: () => ({
    startPipeline: jest.fn().mockResolvedValue({ success: false }),
    loading: false,
  }),
}));

jest.mock('../contexts/WebSocketContext', () => ({
  useWebSocketContext: () => ({
    connectToRun: jest.fn(),
  }),
}));

import DataUpload from '../pages/DataUpload';

describe('DataUpload page', () => {
  test('renders upload headings and submit button', () => {
    render(
      <MemoryRouter future={ROUTER_FUTURE}>
        <DataUpload />
      </MemoryRouter>
    );

    expect(
      screen.getByRole('heading', { name: /data upload/i })
    ).toBeInTheDocument();

    expect(
      screen.getByRole('button', { name: /start biomarker pipeline/i })
    ).toBeInTheDocument();
  });
});

