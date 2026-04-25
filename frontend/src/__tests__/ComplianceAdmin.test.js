import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ROUTER_FUTURE } from '../routerFuture';
import ComplianceAdmin from '../pages/ComplianceAdmin';

const mockListChecklistItems = jest.fn();
const mockPatchChecklistItem = jest.fn();

jest.mock('../contexts/AuthContext', () => {
  const adminUser = { id: 'admin-1', role: 'admin', email: 'a@example.com' };
  return {
    useAuth: () => ({
      user: adminUser,
      loading: false,
    }),
  };
});

jest.mock('../services/api', () => ({
  api: {
    admin: {
      compliance: {
        listChecklistItems: (...args) => mockListChecklistItems(...args),
        createChecklistItem: jest.fn(() => Promise.resolve({ data: { id: 'new' } })),
        patchChecklistItem: (...args) => mockPatchChecklistItem(...args),
      },
    },
  },
}));

function renderPage() {
  return render(
    <MemoryRouter future={ROUTER_FUTURE} initialEntries={['/admin/compliance']}>
      <Routes>
        <Route path="/admin/compliance" element={<ComplianceAdmin />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('ComplianceAdmin', () => {
  beforeEach(() => {
    mockListChecklistItems.mockReset();
    mockPatchChecklistItem.mockReset();
    mockListChecklistItems.mockResolvedValue({
      data: {
        items: [
          {
            id: 'item-1',
            framework: 'hipaa',
            control_code: '164.308',
            title: 'Access control',
            status: 'open',
            evidence_link: null,
            notes: null,
          },
        ],
      },
    });
    mockPatchChecklistItem.mockResolvedValue({ data: { id: 'item-1', status: 'complete' } });
  });

  test('loads checklist and saves a row', async () => {
    renderPage();
    await waitFor(() => expect(mockListChecklistItems).toHaveBeenCalled());
    expect(await screen.findByText('Access control')).toBeInTheDocument();

    const statusSelect = screen.getByLabelText(/status for 164.308/i);
    await userEvent.selectOptions(statusSelect, 'complete');

    const evidence = screen.getByLabelText(/evidence link for 164.308/i);
    await userEvent.clear(evidence);
    await userEvent.type(evidence, 'https://example.com/proof/164.308');

    await userEvent.click(screen.getByRole('button', { name: /^save$/i }));

    await waitFor(() => expect(mockPatchChecklistItem).toHaveBeenCalled());
    expect(mockPatchChecklistItem).toHaveBeenCalledWith(
      'item-1',
      expect.objectContaining({
        status: 'complete',
        evidence_link: 'https://example.com/proof/164.308',
      })
    );
  });
});
