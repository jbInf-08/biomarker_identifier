import React, { act } from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, useNavigate } from 'react-router-dom';
import { ROUTER_FUTURE } from '../routerFuture';
import Header from '../components/Layout/Header';
import { useAuth } from '../contexts/AuthContext';

vi.mock('../services/api', () => ({
  apiClient: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}));
vi.mock('../contexts/AuthContext');
vi.mock('react-router-dom', async () => ({
  ...(await vi.importActual('react-router-dom')),
  useNavigate: vi.fn(),
}));

describe('Header component', () => {
  const mockLogout = vi.fn();
  const mockNavigate = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    useAuth.mockReturnValue({
      user: { name: 'Test User', email: 'test@example.com', role: 'researcher' },
      logout: mockLogout,
    });
    useNavigate.mockReturnValue(mockNavigate);
  });

  test('renders app title', () => {
    render(
      <MemoryRouter future={ROUTER_FUTURE}>
        <Header onMenuClick={vi.fn()} />
      </MemoryRouter>
    );
    expect(
      screen.getByRole('heading', { name: /cancer biomarker identifier/i })
    ).toBeInTheDocument();
  });

  test('renders user name when available', () => {
    render(
      <MemoryRouter future={ROUTER_FUTURE}>
        <Header onMenuClick={vi.fn()} />
      </MemoryRouter>
    );
    expect(screen.getByText('Test User')).toBeInTheDocument();
  });

  test('opens user menu on click', async () => {
    render(
      <MemoryRouter future={ROUTER_FUTURE}>
        <Header onMenuClick={vi.fn()} />
      </MemoryRouter>
    );
    const userButton = screen.getByRole('button', { name: /user menu/i });
    await act(async () => {
      await userEvent.click(userButton);
    });
    expect(screen.getByText('Profile')).toBeInTheDocument();
    expect(screen.getByText('Sign out')).toBeInTheDocument();
  });

  test('calls onMenuClick when menu button clicked', async () => {
    const onMenuClick = vi.fn();
    render(
      <MemoryRouter future={ROUTER_FUTURE}>
        <Header onMenuClick={onMenuClick} />
      </MemoryRouter>
    );
    const buttons = screen.getAllByRole('button');
    const menuButton = buttons[0];
    await act(async () => {
      await userEvent.click(menuButton);
    });
    expect(onMenuClick).toHaveBeenCalled();
  });
});
