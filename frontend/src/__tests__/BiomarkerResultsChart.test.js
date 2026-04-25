import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import BiomarkerResultsChart from '../components/Visualizations/BiomarkerResultsChart';

jest.mock('recharts', () => ({
  BarChart: ({ children }) => <div data-testid="bar-chart">{children}</div>,
  Bar: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  Legend: () => null,
  ResponsiveContainer: ({ children }) => <div>{children}</div>,
  ScatterChart: ({ children }) => <div data-testid="scatter-chart">{children}</div>,
  Scatter: () => null,
  LineChart: ({ children }) => <div data-testid="line-chart">{children}</div>,
  Line: () => null,
  PieChart: ({ children }) => <div data-testid="pie-chart">{children}</div>,
  Pie: () => null,
  Cell: () => null,
}));

const mockData = [
  { gene_symbol: 'TP53', p_value: 0.001, effect_size: 1.5, fold_change: 2.0 },
  { gene_symbol: 'KRAS', p_value: 0.01, effect_size: 1.2, fold_change: 1.8 },
  { gene_symbol: 'BRCA1', p_value: 0.05, effect_size: 0.9, fold_change: 1.5 },
];

describe('BiomarkerResultsChart', () => {
  test('renders default title when no title prop', () => {
    render(<BiomarkerResultsChart data={mockData} />);
    expect(
      screen.getByText(/biomarker analysis results/i)
    ).toBeInTheDocument();
  });

  test('renders custom title', () => {
    render(
      <BiomarkerResultsChart data={mockData} title="My Custom Chart" />
    );
    expect(screen.getByText('My Custom Chart')).toBeInTheDocument();
  });

  test('renders chart type options', () => {
    render(<BiomarkerResultsChart data={mockData} />);
    expect(screen.getByText(/bar chart/i)).toBeInTheDocument();
    expect(screen.getByText(/scatter plot/i)).toBeInTheDocument();
  });

  test('handles empty data', () => {
    render(<BiomarkerResultsChart data={[]} />);
    expect(
      screen.getByText(/no biomarker data available for visualization/i)
    ).toBeInTheDocument();
  });

  test('handles null/undefined data', () => {
    render(<BiomarkerResultsChart data={null} />);
    expect(
      screen.getByText(/no biomarker data available for visualization/i)
    ).toBeInTheDocument();
  });
});
