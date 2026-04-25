import React, { act } from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, useNavigate } from 'react-router-dom';
import { ROUTER_FUTURE } from '../routerFuture';
import Header from '../components/Layout/Header';
import { useAuth } from '../contexts/AuthContext';

jest.mock('../services/api', () => ({
  apiClient: { get: jest.fn(), post: jest.fn(), delete: jest.fn() },
}));
jest.mock('../contexts/AuthContext');
jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useNavigate: jest.fn(),
}));

describe('Header component', () => {
  const mockLogout = jest.fn();
  const mockNavigate = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    useAuth.mockReturnValue({
      user: { name: 'Test User', email: 'test@example.com', role: 'researcher' },
      logout: mockLogout,
    });
    useNavigate.mockReturnValue(mockNavigate);
  });

  test('renders app title', () => {
    render(
      <MemoryRouter future={ROUTER_FUTURE}>
        <Header onMenuClick={jest.fn()} />
      </MemoryRouter>
    );
    expect(
      screen.getByRole('heading', { name: /cancer biomarker identifier/i })
    ).toBeInTheDocument();
  });

  test('renders user name when available', () => {
    render(
      <MemoryRouter future={ROUTER_FUTURE}>
        <Header onMenuClick={jest.fn()} />
      </MemoryRouter>
    );
    expect(screen.getByText('Test User')).toBeInTheDocument();
  });

  test('opens user menu on click', async () => {
    render(
      <MemoryRouter future={ROUTER_FUTURE}>
        <Header onMenuClick={jest.fn()} />
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
    const onMenuClick = jest.fn();
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
