import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ROUTER_FUTURE } from '../routerFuture';
import Models from '../pages/Models';

describe('Models page', () => {
  test('renders ML Models heading', () => {
    render(
      <MemoryRouter future={ROUTER_FUTURE}>
        <Models />
      </MemoryRouter>
    );
    expect(
      screen.getByRole('heading', { name: /ML Models/i })
    ).toBeInTheDocument();
  });

  test('renders View Results link', () => {
    render(
      <MemoryRouter future={ROUTER_FUTURE}>
        <Models />
      </MemoryRouter>
    );
    const link = screen.getByRole('link', { name: /view results/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute('href', '/results');
  });

  test('renders model training section', () => {
    render(
      <MemoryRouter future={ROUTER_FUTURE}>
        <Models />
      </MemoryRouter>
    );
    expect(screen.getByText(/train and manage machine learning models/i)).toBeInTheDocument();
    expect(screen.getByText(/model training/i)).toBeInTheDocument();
  });
});
