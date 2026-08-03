import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ROUTER_FUTURE } from '../routerFuture';
import Settings from '../pages/Settings';

describe('Settings page', () => {
  test('renders Settings heading', () => {
    render(
      <MemoryRouter future={ROUTER_FUTURE}>
        <Settings />
      </MemoryRouter>
    );
    expect(
      screen.getByRole('heading', { name: /^Settings$/i })
    ).toBeInTheDocument();
  });

  test('renders configure preferences text', () => {
    render(
      <MemoryRouter future={ROUTER_FUTURE}>
        <Settings />
      </MemoryRouter>
    );
    expect(
      screen.getByText(/configure your application preferences/i)
    ).toBeInTheDocument();
  });

  test('renders settings coming soon message', () => {
    render(
      <MemoryRouter future={ROUTER_FUTURE}>
        <Settings />
      </MemoryRouter>
    );
    expect(
      screen.getByText(/settings coming soon/i)
    ).toBeInTheDocument();
  });
});
