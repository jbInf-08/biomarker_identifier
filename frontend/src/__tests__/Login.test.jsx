import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ROUTER_FUTURE } from '../routerFuture';
import { useAuth } from '../contexts/AuthContext';
import Login from '../pages/Login';

vi.mock('../services/api', () => ({
  apiClient: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}));
vi.mock('../contexts/AuthContext');
vi.mock('react-router-dom', async () => ({
  ...(await vi.importActual('react-router-dom')),
  useNavigate: () => vi.fn(),
}));

function renderLogin() {
  return render(
    <MemoryRouter future={ROUTER_FUTURE}>
      <Login />
    </MemoryRouter>
  );
}

describe('Login page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuth.mockReturnValue({
      login: vi.fn().mockResolvedValue({ success: true }),
      register: vi.fn().mockResolvedValue({ success: true }),
      isAuthenticated: false,
    });
  });

  test('renders sign in form by default', () => {
    renderLogin();
    expect(screen.getByRole('heading', { name: /sign in to your account/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/email address/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
  });

  test('switches to create account form', () => {
    renderLogin();
    fireEvent.click(screen.getByRole('button', { name: /create a new account/i }));
    expect(screen.getByRole('heading', { name: /create your account/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/full name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument();
  });

  test('calls login on sign in submit', async () => {
    const mockLoginFn = vi.fn().mockResolvedValue({ success: true });
    useAuth.mockReturnValue({
      login: mockLoginFn,
      register: vi.fn(),
      isAuthenticated: false,
    });
    renderLogin();
    fireEvent.change(screen.getByPlaceholderText(/enter your email/i), {
      target: { value: 'test@example.com', name: 'email' },
    });
    fireEvent.change(screen.getByPlaceholderText(/enter your password/i), {
      target: { value: 'password123', name: 'password' },
    });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(mockLoginFn).toHaveBeenCalledWith('test@example.com', 'password123');
    });
  });

  test('renders password and confirm password when in register mode', () => {
    renderLogin();
    fireEvent.click(screen.getByRole('button', { name: /create a new account/i }));
    expect(screen.getByPlaceholderText(/enter your password/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/confirm your password/i)).toBeInTheDocument();
  });
});
