import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { CompanyTeams } from '../CompanyTeams';

test('a username can never select the whole-team deletion operation', async () => {
  const client = {
    companyTeams: jest.fn().mockResolvedValue({ canManage: true, teams: [{ id: 't-test', name: 'Platform', description: '', updatedAt: '2026-09-10T00:00:00Z', assignments: [] }] }),
    removeCompanyMember: jest.fn().mockResolvedValue({}), deleteCompanyTeam: jest.fn(),
  };
  render(<CompanyTeams client={client} />);
  fireEvent.click(await screen.findByText('Platform'));
  fireEvent.change(screen.getByLabelText('Member username'), { target: { value: 'delete-team' } });
  fireEvent.click(screen.getByText('Remove assignment by username'));
  expect(screen.getByText('Remove the team assignment for @delete-team?')).toBeTruthy();
  fireEvent.click(screen.getByText('Confirm deletion'));
  await waitFor(() => expect(client.removeCompanyMember).toHaveBeenCalledWith('t-test', 'delete-team'));
  expect(client.deleteCompanyTeam).not.toHaveBeenCalled();
});
