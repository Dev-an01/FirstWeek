# Personal Site

Project case studies, public writing and private learning notes.

## About
Personal Site is a Next.js portfolio with project case studies, a public blog and private learning logs. It is the intended future host for an embeddable public FirstWeek project assistant. Its private notes are outside the FirstWeek corpus.

## Technology stack

Next.js, React, TypeScript, MongoDB.

## Architecture
The App Router organizes pages and API handlers under `src/app`. Components support project and blog browsing, editing and navigation. Project case studies are backed by a version-controlled JSON collection. MongoDB-related code supports writing and learning-log persistence. Authentication code protects private and editing workflows.

## Integration point for FirstWeek
A future portfolio widget should call a public, rate-limited FirstWeek collection API containing explicitly published project summaries. It must never include an internal service token or gain access to the private onboarding index. Publication is a separate deliberate operation, not a side effect of indexing a repository.

## Where to start
Read `src/lib/projects.ts` and `src/app/api/projects/route.ts` to understand project content delivery. Follow `src/components/ProjectDetailClient.tsx` for the case-study experience. Read the README for local development and its documented deployment setup.

## Current limitations
The local case-study collection and README contain different deployment descriptions. Actual current hosting has not been established here, so this document makes no claim that the site is presently deployed to a particular provider. Personal contributions listed in portfolio copy are self-described evidence, not independently audited attribution.

## Ownership
The README identifies the site as Anand Jaiswal's personal site. That attribution does not establish responsibility for every project described on it.

## Architecture flow
Project case studies use a version-controlled collection. Writing and private learning notes use a separate persistence path; private notes are not indexed by FirstWeek.

- Site visitor → Next.js App Router: browse.
- Next.js App Router → Project collection: case studies.
- Next.js App Router → Protected workflows: private / editing.
- Protected workflows → MongoDB: protected content.

## Evidence
- `personal-site/README.md`
- `personal-site/package.json`
- `personal-site/src/lib/projects.ts`
- `personal-site/src/app/api/projects/route.ts`
