"""Private local corpus index. No network or model calls unless --semantic is set.

python3 -m RAG.firstweek.index build --company local-workspace
python3 -m RAG.firstweek.index search --company local-workspace --project moneyplant 'transaction flow'
"""
import argparse
from contextlib import closing
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import tempfile

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CORPUS = ROOT / 'knowledge' / 'firstweek'
DEFAULT_INDEX = ROOT / '.firstweek' / 'knowledge.sqlite3'
STOPWORDS = set('a an and are as at be by can do does for from how i in is it me of on or project tell that the this to was what when where which who why with you your'.split())


def contained_file(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError('Corpus source must be a file inside its root')
    return path


def sections(content):
    heading, lines = 'Overview', []
    for line in content.splitlines():
        if line.startswith('## '):
            if lines:
                yield heading, '\n'.join(lines).strip()
            heading, lines = line[3:].strip(), []
        else:
            lines.append(line)
    if lines:
        yield heading, '\n'.join(lines).strip()


def embedding_model():
    # Import only on explicit semantic use; reuse the existing RAG model manager.
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from embedding_generation.model_manager import get_shared_embedding_model
    options = {'device': 'cpu'}
    if os.environ.get('FIRSTWEEK_EMBEDDING_MODEL'):
        options['model_name'] = os.environ['FIRSTWEEK_EMBEDDING_MODEL']
    return get_shared_embedding_model(**options)


def build(corpus=DEFAULT_CORPUS, destination=DEFAULT_INDEX, company_id=None, model=None):
    if not company_id or not isinstance(company_id, str):
        raise ValueError('An explicit company ID is required')
    corpus, destination = Path(corpus), Path(destination)
    manifest = json.loads(contained_file(corpus, 'manifest.json').read_text())
    if manifest.get('visibility') != 'private':
        raise ValueError('This importer only accepts private corpora')
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='knowledge-', suffix='.sqlite3', dir=destination.parent)
    os.close(fd)
    count, seen = 0, set()
    try:
        with closing(sqlite3.connect(temporary)) as db, db:
            db.executescript('''
                CREATE TABLE projects(company_id TEXT NOT NULL, id TEXT NOT NULL,
                  name TEXT NOT NULL, summary TEXT NOT NULL, stack TEXT NOT NULL, architecture TEXT NOT NULL,
                  PRIMARY KEY(company_id,id));
                CREATE TABLE documents(id TEXT PRIMARY KEY, company_id TEXT NOT NULL,
                  project_id TEXT NOT NULL, title TEXT NOT NULL, content TEXT NOT NULL,
                  sha256 TEXT NOT NULL, evidence TEXT NOT NULL, snapshot_at TEXT NOT NULL,
                  FOREIGN KEY(company_id,project_id) REFERENCES projects(company_id,id));
                CREATE TABLE chunks(id INTEGER PRIMARY KEY, company_id TEXT NOT NULL,
                  project_id TEXT NOT NULL, document_id TEXT NOT NULL REFERENCES documents(id),
                  heading TEXT NOT NULL, content TEXT NOT NULL, embedding TEXT);
                CREATE INDEX chunk_scope ON chunks(company_id,project_id);
                CREATE INDEX document_scope ON documents(company_id,project_id);
                CREATE VIRTUAL TABLE chunk_fts USING fts5(heading,content,tokenize='porter unicode61');
                CREATE TABLE settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            ''')
            db.execute('PRAGMA foreign_keys=ON')
            db.executemany('INSERT INTO settings VALUES (?,?)', [
                ('retrieval', 'hybrid' if model else 'full-text'),
                ('embedding_model', getattr(model, 'model_name', '') if model else ''),
            ])
            for project in manifest['projects']:
                pid = project['id']
                if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,79}', pid) or pid in seen:
                    raise ValueError('Project IDs must be unique URL-safe identifiers')
                seen.add(pid)
                content = contained_file(corpus, project['document']).read_text()
                if len(content.encode()) > 1_000_000:
                    raise ValueError('About document exceeds 1 MB')
                did = hashlib.sha256(f'{company_id}:{pid}:{project["document"]}'.encode()).hexdigest()[:32]
                db.execute('INSERT INTO projects VALUES (?,?,?,?,?,?)',
                           (company_id, pid, project['name'], project['summary'], json.dumps(project['stack']), json.dumps(project.get('architecture'))))
                db.execute('INSERT INTO documents VALUES (?,?,?,?,?,?,?,?)',
                           (did, company_id, pid, project['name'] + ' — project guide', content,
                            hashlib.sha256(content.encode()).hexdigest(), json.dumps(project['evidence']), manifest['snapshotAt']))
                for heading, text in sections(content):
                    if not text or heading == 'Evidence':
                        continue
                    # Bound long sections; current curated guides have short semantic sections.
                    for offset in range(0, len(text), 1400):
                        chunk = text[offset:offset + 1600]
                        vector = model.generate_embedding(f'{project["name"]}: {heading}\n{chunk}').tolist() if model else None
                        cursor = db.execute('INSERT INTO chunks(company_id,project_id,document_id,heading,content,embedding) VALUES (?,?,?,?,?,?)',
                                            (company_id, pid, did, heading, chunk, json.dumps(vector) if vector is not None else None))
                        db.execute('INSERT INTO chunk_fts(rowid,heading,content) VALUES (?,?,?)', (cursor.lastrowid, heading, chunk))
                        count += 1
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return {'projects': len(seen), 'chunks': count, 'retrieval': 'hybrid' if model else 'full-text'}


def connect(path=DEFAULT_INDEX):
    path = Path(path).resolve()
    if not path.is_file():
        raise FileNotFoundError('FirstWeek knowledge index has not been built')
    db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    return db


def project(db, company_id, project_id):
    row = db.execute('SELECT * FROM projects WHERE company_id=? AND id=?', (company_id, project_id)).fetchone()
    if row is None:
        raise LookupError('Project not found')
    value = dict(row)
    value['stack'] = json.loads(value['stack'])
    value['architecture'] = json.loads(value['architecture'])
    value['documents'] = [dict(r) for r in db.execute(
        'SELECT id,title,sha256,snapshot_at FROM documents WHERE company_id=? AND project_id=?', (company_id, project_id))]
    return value


def document(db, company_id, project_id, document_id):
    row = db.execute('SELECT * FROM documents WHERE company_id=? AND project_id=? AND id=?',
                     (company_id, project_id, document_id)).fetchone()
    if row is None:
        raise LookupError('Document not found')
    value = dict(row)
    value['evidence'] = json.loads(value['evidence'])
    return value


def cosine(left, right):
    if len(left) != len(right):
        raise ValueError('Embedding dimensions differ; rebuild the index')
    denominator = math.sqrt(sum(v*v for v in left) * sum(v*v for v in right))
    return sum(a*b for a,b in zip(left,right)) / denominator if denominator else 0


def search(db, company_id, project_id, query, limit=5, model=None):
    project(db, company_id, project_id)
    if not isinstance(query, str) or not query.strip() or len(query) > 2000:
        raise ValueError('Question must contain 1–2000 characters')
    terms = [t for t in re.findall(r'\w+', query.casefold()) if t not in STOPWORDS][:32]
    if not terms and not model:
        return []
    expression = ' OR '.join('"' + term + '"' for term in terms)
    lexical = db.execute('''SELECT c.*,bm25(chunk_fts,2,1) AS rank FROM chunk_fts
        JOIN chunks c ON c.id=chunk_fts.rowid
        WHERE chunk_fts MATCH ? AND c.company_id=? AND c.project_id=?
        ORDER BY rank LIMIT 30''', (expression, company_id, project_id)).fetchall() if terms else []
    scores, candidates = {}, {}
    for rank, row in enumerate(lexical):
        candidates[row['id']] = row
        scores[row['id']] = 1 / (60 + rank + 1)
    if model:
        recorded = db.execute("SELECT value FROM settings WHERE key='embedding_model'").fetchone()['value']
        if recorded != model.model_name:
            raise ValueError('Embedding model changed; rebuild the index with --semantic')
        query_vector = model.generate_embedding(query).tolist()
        # ponytail: exact scan within one project; move to pgvector for large corpora.
        semantic = [(cosine(query_vector,json.loads(r['embedding'])), r) for r in db.execute(
            'SELECT * FROM chunks WHERE company_id=? AND project_id=? AND embedding IS NOT NULL', (company_id, project_id))]
        for rank, (similarity, row) in enumerate(sorted(semantic, key=lambda item:item[0], reverse=True)[:30]):
            if similarity < 0.4:
                continue
            candidates[row['id']] = row
            scores[row['id']] = scores.get(row['id'],0) + 1 / (60 + rank + 1)
    results = []
    for cid in sorted(scores, key=scores.get, reverse=True)[:max(1,min(limit,8))]:
        row = candidates[cid]
        results.append({'id': str(cid), 'documentId': row['document_id'], 'heading': row['heading'],
                        'content': row['content'], 'score': round(scores[cid],6), 'projectId': project_id})
    return results


def check_evidence(corpus=DEFAULT_CORPUS, source_root=None):
    manifest = json.loads((Path(corpus)/'manifest.json').read_text())
    source_root = Path(source_root or manifest['sourceRoot'])
    changes=[]
    for item in manifest['projects']:
        for source in item['evidence']:
            try:
                digest=hashlib.sha256(contained_file(source_root,source['path']).read_bytes()).hexdigest()
                state='changed' if digest != source['sha256'] else 'unchanged'
            except (ValueError,OSError):
                state='missing'
            if state != 'unchanged':
                changes.append({'projectId':item['id'],'path':source['path'],'status':state})
    return changes


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['build','search','check'])
    parser.add_argument('query',nargs='?')
    parser.add_argument('--corpus',type=Path,default=DEFAULT_CORPUS)
    parser.add_argument('--index',type=Path,default=DEFAULT_INDEX)
    parser.add_argument('--company')
    parser.add_argument('--project')
    parser.add_argument('--semantic',action='store_true',help='Load the existing RAG embedding model (may download weights)')
    args=parser.parse_args()
    if args.command=='check':
        result=check_evidence(args.corpus)
        print(json.dumps({'changedSources':result},indent=2))
        raise SystemExit(bool(result))
    if not args.company:
        parser.error('--company is required')
    model=embedding_model() if args.semantic else None
    if args.command=='build':
        print(json.dumps(build(args.corpus,args.index,args.company,model)))
    else:
        if not args.project or not args.query:
            parser.error('search requires --project and a question')
        db=connect(args.index)
        try:
            print(json.dumps(search(db,args.company,args.project,args.query,model=model),indent=2))
        finally:
            db.close()


if __name__=='__main__':
    main()
