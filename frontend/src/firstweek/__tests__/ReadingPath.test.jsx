import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { ReadingPath } from '../ReadingPath';

const step = (id, title, position) => ({ id, title, description: '', documentId: `m-${id}`, focus: null, experience: null, position, revision: 0, completed: false });

test('maintainers can edit and atomically reorder maintained reading steps', async () => {
  const first = step('r-00000000-0000-4000-8000-000000000001', 'First', 0);
  const second = step('r-00000000-0000-4000-8000-000000000002', 'Second', 1);
  const client = {
    readingPath: jest.fn().mockResolvedValue({ canManage: true, steps: [first, second], managedSteps: [first, second], completed: 0, total: 2 }),
    saveReadingStep: jest.fn().mockResolvedValue({}), reorderReadingSteps: jest.fn().mockResolvedValue({}),
  };
  render(<ReadingPath project={{ id: 'project-test', membershipRole: 'MAINTAINER', documents: [{ id: first.documentId, title: 'One', managed: true }, { id: second.documentId, title: 'Two', managed: true }] }} client={client} onSource={() => {}} />);
  fireEvent.click((await screen.findAllByText('Edit'))[0]);
  fireEvent.change(screen.getByLabelText('Step title'), { target: { value: 'First revised' } });
  fireEvent.click(screen.getByText('Save step'));
  await waitFor(() => expect(client.saveReadingStep).toHaveBeenCalledWith('project-test', first.id, expect.objectContaining({ title: 'First revised' })));
  fireEvent.click(await screen.findByLabelText('Move First up'));
  expect(client.reorderReadingSteps).not.toHaveBeenCalled();
  fireEvent.click(screen.getByLabelText('Move First down'));
  await waitFor(() => expect(client.reorderReadingSteps).toHaveBeenCalledWith('project-test', [second.id, first.id]));
});

test('fresh reading-path authority hides controls after a maintainer is demoted', async () => {
  const first = step('r-00000000-0000-4000-8000-000000000001', 'First', 0);
  const client = { readingPath: jest.fn().mockResolvedValue({ canManage: false, steps: [first], completed: 0, total: 1 }) };
  render(<ReadingPath project={{ id: 'project-test', membershipRole: 'MAINTAINER', documents: [{ id: first.documentId, title: 'One', managed: true }] }} client={client} onSource={() => {}} />);
  expect(await screen.findByText('First')).toBeInTheDocument();
  expect(screen.queryByText('Add a reading step')).not.toBeInTheDocument();
  expect(screen.queryByText('Edit')).not.toBeInTheDocument();
});
