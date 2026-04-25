import React from 'react';
import { render, screen } from '@testing-library/react';
import PathwayAnalysisChart from '../components/Visualizations/PathwayAnalysisChart';

jest.mock('recharts', () => ({
  BarChart: ({ children }) => <div data-testid="bar-chart">{children}</div>,
  Bar: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  Legend: () => null,
  ResponsiveContainer: ({ children }) => <div>{children}</div>,
  Treemap: ({ children }) => <div data-testid="treemap">{children}</div>,
  Cell: () => null,
  ScatterChart: ({ children }) => <div data-testid="scatter-chart">{children}</div>,
  Scatter: () => null,
}));

const mockData = [
  {
    pathway_name: 'Cell Cycle',
    p_value: 0.001,
    enrichment_score: 1.2,
    gene_count: 50,
    pathway_size: 200,
  },
  {
    pathway_name: 'Apoptosis',
    p_value: 0.01,
    enrichment_score: 0.8,
    gene_count: 30,
    pathway_size: 150,
  },
];

describe('PathwayAnalysisChart', () => {
  test('renders default title', () => {
    render(<PathwayAnalysisChart data={mockData} />);
    expect(
      screen.getByText(/pathway analysis results/i)
    ).toBeInTheDocument();
  });

  test('renders custom title', () => {
    render(
      <PathwayAnalysisChart data={mockData} title="Enrichment Overview" />
    );
    expect(screen.getByText('Enrichment Overview')).toBeInTheDocument();
  });

  test('handles empty data', () => {
    render(<PathwayAnalysisChart data={[]} />);
    expect(
      screen.getByText(/no pathway analysis data available for visualization/i)
    ).toBeInTheDocument();
  });

  test('handles null data', () => {
    render(<PathwayAnalysisChart data={null} />);
    expect(
      screen.getByText(/no pathway analysis data available for visualization/i)
    ).toBeInTheDocument();
  });

  test('renders filter options', () => {
    render(<PathwayAnalysisChart data={mockData} />);
    expect(screen.getByText(/bar chart/i)).toBeInTheDocument();
  });
});
