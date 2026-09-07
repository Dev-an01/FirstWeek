// Development-only fictional fixture. This module is eliminated from production builds.
import Workspace from './Workspace';

const id = 'northstar-api';
const documentId = 'a'.repeat(32);
const content = `# Northstar API — project guide

This is fictional content for the FirstWeek development preview.

## About
Northstar API is an example service that accepts customer events and makes them available to internal reporting tools. The project separates event ingestion from processing so a busy consumer does not slow down the request path.

## Architecture
Requests arrive at an HTTP API. The API validates each event, assigns an event ID, and places it on a queue. A worker consumes queued events and writes normalized records to PostgreSQL. A separate read endpoint returns the processed records.

## Where to start
Read the HTTP handler first, then follow an event through the queue worker. Compare the input schema with the stored record. Run the example tests before changing validation behavior.

## Current limitations
This is a fictional example, not a running customer service. No production usage, team assignments, or performance measurements are claimed.

## Ownership
Responsibilities have not been assigned in this preview.`;
const project = {
  id,
  name: 'Northstar API',
  summary: 'Event ingestion and reporting for internal teams',
  stack: ['TypeScript', 'Node.js', 'PostgreSQL'],
  documents: [
    {
      id: documentId,
      title: 'Northstar API — project guide',
      snapshot_at: '2026-09-07T00:00:00Z',
    },
  ],
};
async function result(value, signal) {
  if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');
  await new Promise((resolve) => {
    setTimeout(resolve, 180);
  });
  if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');
  return value;
}
const previewApi = {
  projects: (signal) =>
    result(
      { projects: [{ id, name: project.name, description: project.summary }] },
      signal
    ),
  project: (pid, signal) =>
    pid === id
      ? result(project, signal)
      : Promise.reject(
          new Error('This fictional project is not in the preview.')
        ),
  document: (pid, did, signal) =>
    pid === id && did === documentId
      ? result(
          { content, snapshot_at: '2026-09-07T00:00:00Z', evidence: [] },
          signal
        )
      : Promise.reject(new Error('Source not found.')),
  members: (pid, signal) => result({ members: [] }, signal),
  ask: (pid, question, signal) => {
    if (pid !== id) return Promise.reject(new Error('Project not found.'));
    const heading = /start|read/i.test(question)
      ? 'Where to start'
      : /limit/i.test(question)
        ? 'Current limitations'
        : /owner|who|responsib/i.test(question)
          ? 'Ownership'
          : /work|architect|event|queue/i.test(question)
            ? 'Architecture'
            : null;
    if (!heading)
      return result(
        {
          mode: 'no-evidence',
          answer:
            'This fictional preview has no matching evidence. Try asking how the project works.',
          sources: [],
        },
        signal
      );
    const excerpt = content
      .split(`## ${heading}\n`)[1]
      .split('\n## ')[0]
      .trim();
    return result(
      {
        mode: 'source-excerpts',
        answer: `[1] ${excerpt}`,
        sources: [
          { id: '1', heading, content: excerpt, documentId, projectId: id },
        ],
      },
      signal
    );
  },
};
export default function Preview() {
  return <Workspace client={previewApi} preview />;
}
