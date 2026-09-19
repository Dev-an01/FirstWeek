import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import Workspace from '../Workspace';
import * as privateApi from '../../services/api';
import { initializePrivateAuth, useAuthStore } from '../../store/authStore';
import { simulateBroadcast } from '../../test/utils/testUtils';

jest.mock('react-markdown', () => ({ __esModule: true, default: ({ children }) => <div>{children}</div> }));
jest.mock('../../services/api');

const project = { id: 'example', name: 'Example project', description: 'Public summary', summary: 'Public summary', stack: ['React'],
  status: 'Completed', tags: [], membershipRole: 'MAINTAINER',
  documents: [{ id: 'guide', title: 'Public guide', managed: true }] };
const client = () => ({
  projects: jest.fn().mockResolvedValue({ projects: [project], canCreate: true }),
  project: jest.fn().mockResolvedValue(project),
  document: jest.fn().mockResolvedValue({ content: 'Public architecture evidence.' }),
  ask: jest.fn().mockResolvedValue({ answer: 'A sourced explanation [1].', sources: [{ id: 'section', documentId: 'guide', heading: 'Architecture' }], mode: 'generated' }),
  companyTeams: jest.fn(), createProject: jest.fn(), onboardingProfile: jest.fn(), conversations: jest.fn(),
});
function show(api, path = '/showcase') {
  return render(<MemoryRouter initialEntries={[path]}><Routes><Route path="/showcase/:projectId?/:view?" element={<Workspace client={api} publicAccess />} /></Routes></MemoryRouter>);
}
beforeEach(() => {
  jest.clearAllMocks();
  Element.prototype.scrollIntoView = jest.fn();
});

test('anonymous public directory never initializes private auth or exposes management capabilities', async () => {
  const api = client();
  show(api);
  expect((await screen.findAllByText('Example project')).length).toBeGreaterThan(0);
  expect(screen.getByText('Public projects')).toBeInTheDocument();
  expect(screen.getByText('Completed')).toBeInTheDocument();
  expect(screen.queryByText('Create project')).not.toBeInTheDocument();
  expect(screen.queryByText('Company teams')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Sign out' })).not.toBeInTheDocument();
  simulateBroadcast('auth_channel', { type: 'login' });
  await Promise.resolve();
  expect(privateApi.getMe).not.toHaveBeenCalled();
  expect(api.companyTeams).not.toHaveBeenCalled();
});

test('public knowledge stays read-only even if a DTO claims maintainer privileges', async () => {
  show(client(), '/showcase/example/knowledge');
  await screen.findByText('The project, in writing.');
  expect(screen.queryByText('Settings')).not.toBeInTheDocument();
  expect(screen.queryByText('People')).not.toBeInTheDocument();
  expect(screen.queryByText('Onboarding')).not.toBeInTheDocument();
  expect(screen.queryByText('Add a text source')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Delete Public guide' })).not.toBeInTheDocument();
});

test('public chat uses ephemeral turns and opens evidence without saved conversation calls', async () => {
  const api = client();
  show(api, '/showcase/example/ask');
  const input = await screen.findByLabelText('Ask about Example project');
  fireEvent.change(input, { target: { value: 'How does it work?' } });
  fireEvent.click(screen.getByRole('button', { name: 'Send question' }));
  await screen.findByText('A sourced explanation [1].');
  expect(api.ask).toHaveBeenCalledWith('example', 'How does it work?', expect.any(AbortSignal), []);
  expect(api.conversations).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: '1 Architecture' }));
  await screen.findByText('Public architecture evidence.');
  fireEvent.click(screen.getByText('New conversation'));
  expect(screen.queryByText('A sourced explanation [1].')).not.toBeInTheDocument();
});

test('private auth still initializes explicitly and stops listening on cleanup', async () => {
  privateApi.getMe.mockResolvedValue({ data: { user: null } });
  const cleanup = initializePrivateAuth();
  await waitFor(() => expect(privateApi.getMe).toHaveBeenCalledTimes(1));
  simulateBroadcast('auth_channel', { type: 'login' });
  await waitFor(() => expect(privateApi.getMe).toHaveBeenCalledTimes(2));
  cleanup();
  simulateBroadcast('auth_channel', { type: 'login' });
  await Promise.resolve();
  expect(privateApi.getMe).toHaveBeenCalledTimes(2);
  useAuthStore.setState({ isLoading: false });
});
