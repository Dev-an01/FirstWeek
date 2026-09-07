import json
from pathlib import Path
import tempfile
import unittest
from .index import build, connect, document, project, search


class IndexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.index = self.root / 'index.sqlite3'
        self.manifest = {'visibility':'private','snapshotAt':'2026-09-07', 'projects':[]}
        for pid in ['alpha','beta']:
            (self.root/f'{pid}.md').write_text(f'# {pid}\n\n## Architecture\nThe {pid} engine uses queues.\n\n## Ownership\nThe owner of {pid} is unknown.')
            self.manifest['projects'].append({'id':pid,'name':pid,'summary':pid,'stack':['Python'],'document':f'{pid}.md','evidence':[]})
        self.save_manifest()
        build(self.root,self.index,'company-a')
        self.db=connect(self.index)

    def save_manifest(self):
        (self.root/'manifest.json').write_text(json.dumps(self.manifest))

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_same_terms_never_cross_project_or_company(self):
        rows=search(self.db,'company-a','alpha','engine queues')
        self.assertTrue(rows)
        self.assertTrue(all('beta' not in r['content'] and r['projectId']=='alpha' for r in rows))
        for company,pid in [('company-b','alpha'),('company-a','missing'),('', 'alpha')]:
            with self.assertRaises(LookupError):
                search(self.db,company,pid,'engine')

    def test_citation_cannot_read_another_project(self):
        did=project(self.db,'company-a','beta')['documents'][0]['id']
        with self.assertRaises(LookupError):
            document(self.db,'company-a','alpha',did)
        with self.assertRaises(LookupError):
            document(self.db,'company-b','beta',did)
        self.assertIn('beta',document(self.db,'company-a','beta',did)['content'])

    def test_queries_are_bounded_and_fts_syntax_is_not_executed(self):
        self.assertEqual(search(self.db,'company-a','alpha','zzzznotpresent'),[])
        self.assertEqual(search(self.db,'company-a','alpha','" OR *; DROP TABLE chunks;'),[])
        self.assertTrue(search(self.db,'company-a','alpha','queues'))
        for query in ['', ' '*3, 'x'*2001]:
            with self.assertRaises(ValueError):
                search(self.db,'company-a','alpha',query)

    def test_failed_build_preserves_previous_index(self):
        original=self.index.read_bytes()
        self.manifest['projects'][0]['document']='../outside.md'
        self.save_manifest()
        with self.assertRaises(ValueError):
            build(self.root,self.index,'company-a')
        self.assertEqual(self.index.read_bytes(),original)

    def test_symlink_escape_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            target=Path(outside)/'private.md'
            target.write_text('Do not index')
            (self.root/'escape.md').symlink_to(target)
            self.manifest['projects'][0]['document']='escape.md'
            self.save_manifest()
            with self.assertRaises(ValueError):
                build(self.root,self.index,'company-a')

    def test_rebuild_removes_deleted_projects(self):
        self.manifest['projects']=self.manifest['projects'][:1]
        self.save_manifest()
        build(self.root,self.index,'company-a')
        db=connect(self.index)
        try:
            with self.assertRaises(LookupError):
                project(db,'company-a','beta')
        finally:
            db.close()


if __name__=='__main__':
    unittest.main()
