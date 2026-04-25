import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ROUTER_FUTURE } from '../routerFuture';
import Sidebar from '../components/Layout/Sidebar';

describe('Sidebar component', () => {
  test('renders main navigation links', () => {
    render(
      <MemoryRouter future={ROUTER_FUTURE}>
        <Sidebar isOpen={true} onClose={jest.fn()} />
      </MemoryRouter>
    );
    expect(screen.getByRole('link', { name: /dashboard/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /data upload/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /pipeline monitoring/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /results/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /reports/i })).toBeInTheDocument();
  });

  test('renders secondary navigation links', () => {
    render(
      <MemoryRouter future={ROUTER_FUTURE}>
        <Sidebar isOpen={true} onClose={jest.fn()} />
      </MemoryRouter>
    );
    expect(screen.getByRole('link', { name: /clinical databases/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /ml models/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /settings/i })).toBeInTheDocument();
  });

  test('calls onClose when close button clicked', async () => {
    const onClose = jest.fn();
    render(
      <MemoryRouter future={ROUTER_FUTURE}>
        <Sidebar isOpen={true} onClose={onClose} />
      </MemoryRouter>
    );
    const closeButton = screen.getByRole('button', { name: /close sidebar/i });
    await userEvent.click(closeButton);
    expect(onClose).toHaveBeenCalled();
  });

  test('renders app branding from i18n', () => {
    render(
      <MemoryRouter future={ROUTER_FUTURE}>
        <Sidebar isOpen={true} onClose={jest.fn()} />
      </MemoryRouter>
    );
    const branding = screen.getAllByText('Cancer Biomarker Identifier');
    expect(branding.length).toBeGreaterThanOrEqual(1);
  });

  test('renders Tools & Resources section', () => {
    render(
      <MemoryRouter future={ROUTER_FUTURE}>
        <Sidebar isOpen={true} onClose={jest.fn()} />
      </MemoryRouter>
    );
    expect(screen.getByText('Tools & Resources')).toBeInTheDocument();
  });

  test('shows compliance admin link for admin users', () => {
    render(
      <MemoryRouter future={ROUTER_FUTURE}>
        <Sidebar isOpen={true} onClose={jest.fn()} user={{ id: '1', role: 'admin' }} />
      </MemoryRouter>
    );
    expect(screen.getByRole('link', { name: /compliance \(admin\)/i })).toBeInTheDocument();
  });
});
