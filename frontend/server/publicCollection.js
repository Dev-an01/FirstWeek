// Deliberately authored publication snapshot. Never import the private manifest,
// databases, uploads, company directory, profiles, or saved conversations here.
// Editing this file and redeploying is the publication/removal workflow for v1.
const snapshot = '2026-09-17';
const guide = (id, sections) => ({
  id: `${id}-public-guide`, title: 'Public project guide', snapshot_at: snapshot,
  sections: Object.entries(sections).map(([heading, content]) => ({ heading, content })),
  content: Object.entries(sections).map(([heading, content]) => `## ${heading}\n\n${content}`).join('\n\n'),
});
const architecture = (title, caption, components) => ({
  title, caption,
  nodes: components.map(([label, detail], index) => ({ id: `component-${index}`, label, detail, col: index % 3, row: Math.floor(index / 3) })),
  edges: components.slice(1).map(([, detail], index) => ({ source: `component-${index}`, target: `component-${index + 1}`, label: detail })),
});
const project = (id, name, summary, stack, diagram, sections, metadata = {}) => ({
  id, name, summary, description: summary, stack, architecture: diagram,
  visibility: 'public', ...metadata, documents: [guide(id, sections)],
});

export const publicCollection = Object.freeze([
  project('firstweek', 'FirstWeek', 'Project onboarding with inspectable sources and grounded conversation',
    ['React', 'Express', 'FastAPI', 'PostgreSQL', 'OpenAI'],
    architecture('From a question to a sourced answer', 'This diagram describes the separate public showcase. The private workspace retains its membership gateway and database.', [
      ['Public workspace', 'Visitors browse published projects, guides and architecture.'],
      ['Public retrieval', 'The server selects passages only from the chosen published project.'],
      ['Answer or excerpts', 'OpenAI generation uses a system prompt and numbered evidence, with rate-limited Groq and free OpenRouter fallbacks. Offline mode returns source excerpts.'],
    ]), {
      About: 'FirstWeek helps people understand software projects through project guides, visual architecture and source-backed conversation. The public showcase lets visitors browse and ask questions without an account. Visitors cannot create projects, change project knowledge or access the private workspace.',
      Architecture: 'The private application uses React, Express authentication and project membership, PostgreSQL for managed workspace data, and a FastAPI retrieval service. This public demo is isolated: React calls a Node server endpoint that retrieves from a separately authored publication snapshot. When enabled, OpenAI generates answers from selected public evidence; Groq and a free OpenRouter model provide ordered fallbacks. Offline mode returns source excerpts. Public requests do not connect to the private database or private retrieval index.',
      'Where to start': 'Open Overview, follow the Architecture tab, and read the public guide in Knowledge. Ask FirstWeek about the project purpose, components or limitations. Numbered source buttons open the guide behind an answer.',
      'Current limitations': 'Phase 1 is complete and later onboarding features remain in active development. The public demo uses lightweight keyword retrieval, not semantic embeddings. Public conversations exist in browser memory and disappear on reload or navigation away from Ask. Publication changes require editing the public snapshot and redeploying. The personal-site API and embedded widget remain deferred. Production deployment and measured performance are not established by this guide.',
    }, { status: 'Active development', tags: ['Phase 1 complete'] }),
  project('ai-pr-review-agent', 'AI PR Review Agent', 'Repository-grounded pull request review with specialist agents',
    ['Python', 'FastAPI', 'LangGraph', 'Redis', 'Next.js'],
    architecture('From webhook to review findings', 'A summary of the documented workflow; live GitHub posting was not verified.', [
      ['Webhook ingress', 'FastAPI validates GitHub webhook signatures and delivery identity.'],
      ['Redis / ARQ worker', 'Queued jobs separate request acceptance from review execution.'],
      ['Specialists and gate', 'LangGraph fans out review work, aggregates findings and applies review gates.'],
    ]), {
      About: 'AI PR Review Agent organizes repository-grounded pull request review around security, quality, test and documentation specialists. A Next.js dashboard presents repositories, pull requests and review details.',
      Architecture: 'FastAPI receives and validates GitHub webhooks. Redis and ARQ queue review jobs. A worker fetches the diff and invokes a LangGraph fan-out to specialist nodes and an aggregation node. The documented retrieval design combines PostgreSQL full-text and vector retrieval with reciprocal rank fusion. Confidence and human approval gates precede review publication.',
      'Where to start': 'Trace the orchestrator graph and specialist nodes first, then repository ingestion. The application requires separate ingress, worker and dashboard processes; an ingress without its worker is not a complete review pipeline.',
      'Current limitations': 'Live GitHub posting, cloud storage and model behavior were not verified for this snapshot. Real LLM and embedding calls are opt-in in the documented configuration. Production deployment and current component ownership are not established.',
    }, { status: 'Built; deployment unverified', tags: ['Repository-grounded'] }),
  project('rag-builder', 'RAG-Builder', 'A framework-light exploration of document retrieval and generation',
    ['Python', 'Sentence Transformers', 'PyTorch', 'CSV'],
    architecture('From PDF to retrieved context', 'A local educational pipeline, not a hosted multi-tenant service.', [
      ['PDF and text chunks', 'Extract text and split it into retrieval passages.'],
      ['Embedding retrieval', 'Store embeddings in CSV and select top-k matches to a query vector.'],
      ['Response generation', 'Pass the retrieved context to the selected inference path.'],
    ]), {
      About: 'RAG-Builder explores retrieval-augmented generation from the terminal without a high-level RAG framework or vector database. Its pipeline extracts PDF text, splits it, creates embeddings, retrieves matches and generates a response.',
      Architecture: 'Python modules separate text processing, chunks, embeddings and retrieval. The inspected embedding implementation uses Sentence Transformers all-mpnet-base-v2. Retrieval uses dot-product scoring through util.dot_score and selects results with torch.topk. Embeddings are stored in CSV.',
      'Where to start': 'Follow the main program, embedding creation, embedding-model service and retrieval service. The LLM directory provides local and API inference paths.',
      'Current limitations': 'The repository documents a framework-free local pipeline and an owner-authored benchmark claim, but this showcase does not independently reproduce that benchmark. CSV vector storage and linear local retrieval are educational choices, not production-scale ingestion or access controls.',
    }, { status: 'Completed learning project', tags: ['Built from first principles'] }),
  project('moneyplant', 'MoneyPlant', 'Telegram-first transaction capture with a private finance dashboard',
    ['TypeScript', 'Next.js', 'PostgreSQL', 'Drizzle', 'grammY'],
    architecture('From message to dashboard', 'A simplified documented flow. No personal transactions are published here.', [
      ['Telegram bot', 'grammY receives expense and investment messages.'],
      ['Shared core logic', 'Parse amounts, categorize entries and allow a correction window.'],
      ['Database / dashboard', 'Commit transactions to PostgreSQL for the private Next.js dashboard.'],
    ]), {
      About: 'MoneyPlant is a personal finance and investment tracker centered on Telegram capture and a private web dashboard. The documented flow turns short messages into categorized transactions with a five-minute correction window.',
      Architecture: 'A Bun workspace separates the Next.js web application, grammY bot and shared TypeScript packages. PostgreSQL and Drizzle provide persistence. The design parses amounts deterministically, tries keyword categorization first and can use a Claude fallback for ambiguity with the amount masked. Auth.js protects the dashboard, while Drizzle queries keep user data scoped.',
      'Where to start': 'Follow shared core business logic, the database package, bot message handlers and web dashboard routes. Pending entries can be edited or cancelled before they are committed in the documented flow.',
      'Current limitations': 'The repository reports Phase 1 at about 90% complete, with production deployment remaining. Phase 2 multi-tenant hosting, mobile support and privacy-preserving compute have not started. No personal financial records are part of this public collection.',
    }, { status: 'Phase 1 · 90% complete', tags: ['Self-hosted'] }),
  project('personal-site', 'Personal Site', 'Project case studies and public writing with protected editing workflows',
    ['Next.js', 'React', 'TypeScript', 'MongoDB'],
    architecture('Browsing project case studies', 'Public case studies are separate from protected writing and learning-note workflows.', [
      ['Site visitor', 'Browse the portfolio and public writing.'],
      ['Next.js App Router', 'Route pages and API handlers through the application.'],
      ['Project collection', 'Deliver case studies from a version-controlled collection.'],
    ]), {
      About: 'Personal Site is a portfolio containing project case studies and public writing. It also has protected editing and learning-note workflows. Private learning notes are not included in FirstWeek.',
      Architecture: 'Next.js App Router organizes pages and serverless API handlers. Case studies use a version-controlled JSON collection. MongoDB Atlas stores public writing and private learning logs, with authentication protecting private and editing workflows. Static rendering and Vercel delivery keep the public portfolio lightweight.',
      'Where to start': 'Follow the project collection, project API handler and project-detail component to understand how case studies reach visitors.',
      'Current limitations': 'A FirstWeek personal-site API and embedded assistant are future work; this demo only provides chat within FirstWeek itself. Protected content and private notes are outside this public snapshot.',
    }, { status: 'Active portfolio', tags: ['Version-controlled case studies'] }),
  project('learning-rag', 'Learning RAG', 'A movie RAG search engine built from first principles across lexical, semantic, hybrid and multimodal retrieval',
    ['Python', 'BM25', 'Sentence Transformers', 'CLIP', 'OpenRouter'],
    architecture('From a movie query to a grounded answer', 'A completed command-line learning project over a local 5,000-movie dataset.', [
      ['Lexical retrieval', 'Text normalization, an inverted index and BM25 preserve exact and rare-term matches.'],
      ['Semantic and hybrid retrieval', 'MiniLM chunk embeddings combine with BM25 through weighted fusion or Reciprocal Rank Fusion.'],
      ['Reranking and generation', 'Optional rerankers refine candidates before OpenRouter generates an answer from retrieved movies.'],
    ]), {
      About: 'Learning RAG is a completed command-line movie search and retrieval-augmented generation project over 5,000 local movie records. It was self-coded manually by Anand: no vibe coding or AI coding agent was used to write the application code. The product can still call an LLM at runtime for query enhancement, reranking and grounded generation; that runtime feature is separate from how the code was authored.',
      Architecture: 'The project builds text preprocessing, an inverted index, TF-IDF and BM25 before adding MiniLM embeddings and overlapping semantic chunks. It combines lexical and semantic rankings through weighted fusion or Reciprocal Rank Fusion, supports optional LLM and local cross-encoder reranking, and passes the top retrieved movies to OpenRouter for grounded answers. CLIP adds direct image-to-movie retrieval.',
      'Where to start': 'Follow text_utils.py, inverted_index.py, semantic_search.py and hybrid_search.py in that order. Then read query_enhancement.py, augmented_generation_cli.py and evaluation_cli.py to see how retrieval becomes RAG and how precision, recall and F1 are measured.',
      'Current limitations': 'The project is complete as a learning build, not a hosted production service. It uses local files and caches, assumes consecutive movie IDs, has a ten-case golden evaluation set, and does not programmatically validate generated citations. A demo UI and hosting path are documented as future work.',
    }, { status: 'Completed', tags: ['Self-coded', 'No AI coding agents'] }),
]);
