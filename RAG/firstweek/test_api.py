"""Run with the existing RAG dependencies: python -m unittest RAG.firstweek.test_api."""
import os
from unittest import TestCase
from unittest.mock import patch
from fastapi.testclient import TestClient
from .api import app
from .index import DEFAULT_INDEX


class APITests(TestCase):
    def setUp(self):
        self.environment=patch.dict(os.environ, {
            'FIRSTWEEK_SERVICE_TOKEN':'test-only-token-with-at-least-32-characters',
            'FIRSTWEEK_INDEX_PATH':str(DEFAULT_INDEX),
            'FIRSTWEEK_SEMANTIC':'false','FIRSTWEEK_GENERATE':'false',
        })
        self.environment.start()
        self.client=TestClient(app)
        self.headers={'X-FirstWeek-Token':os.environ['FIRSTWEEK_SERVICE_TOKEN']}
        self.base='/internal/firstweek/local-workspace/moneyplant'

    def tearDown(self):
        self.environment.stop()

    def test_token_required_and_misconfiguration_fails_closed(self):
        self.assertEqual(self.client.get(self.base).status_code,401)
        self.assertEqual(self.client.get(self.base,headers={'X-FirstWeek-Token':'wrong'}).status_code,401)
        with patch.dict(os.environ,{'FIRSTWEEK_SERVICE_TOKEN':''}):
            self.assertEqual(self.client.get(self.base,headers=self.headers).status_code,503)

    def test_project_scope_and_document_scope(self):
        response=self.client.get(self.base,headers=self.headers)
        self.assertEqual(response.status_code,200)
        did=response.json()['documents'][0]['id']
        self.assertEqual(self.client.get(self.base+'/documents/'+did,headers=self.headers).status_code,200)
        self.assertEqual(self.client.get('/internal/firstweek/other-company/moneyplant',headers=self.headers).status_code,404)
        self.assertEqual(self.client.get('/internal/firstweek/local-workspace/firstweek/documents/'+did,headers=self.headers).status_code,404)

    def test_excerpt_mode_is_honest_and_ignores_client_scope(self):
        response=self.client.post(self.base+'/ask',headers=self.headers,json={
            'question':'How does transaction categorization work?', 'companyId':'other-company', 'projectId':'FirstWeek', 'role':'SUPER_ADMIN'})
        self.assertEqual(response.status_code,200)
        data=response.json()
        self.assertEqual(data['mode'],'source-excerpts')
        self.assertEqual(data['retrieval'],'full-text')
        self.assertTrue(data['sources'])
        self.assertTrue(all(s['projectId']=='moneyplant' for s in data['sources']))

    def test_no_evidence_and_invalid_input(self):
        response=self.client.post(self.base+'/ask',headers=self.headers,json={'question':'zzzzunfindable'})
        self.assertEqual(response.json()['mode'],'no-evidence')
        for question in ['', '   ', 'a'*2001, 7]:
            self.assertEqual(self.client.post(self.base+'/ask',headers=self.headers,json={'question':question}).status_code,422)

    def test_missing_index_is_recoverable(self):
        with patch.dict(os.environ,{'FIRSTWEEK_INDEX_PATH':'/tmp/firstweek-nonexistent-db.sqlite3'}):
            self.assertEqual(self.client.get(self.base,headers=self.headers).status_code,503)

    def test_natural_stack_question_finds_documented_stack(self):
        response=self.client.post(self.base+'/ask', headers=self.headers, json={
            'question':'hi is the project deployed what are the tech stack used'})
        self.assertEqual(response.status_code,200)
        self.assertIn('Technology stack', [s['heading'] for s in response.json()['sources']])

    def test_generation_uses_evidence_and_bounded_conversation(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        client=Mock()
        client.generate.return_value=SimpleNamespace(content='The web app uses Next.js. [1]')
        with patch.dict(os.environ,{'FIRSTWEEK_GENERATE':'true'}), patch('RAG.firstweek.api.llm_client',return_value=client):
            response=self.client.post(self.base+'/ask',headers=self.headers,json={
                'question':'And the database?', 'history':[
                    {'role':'user','content':'What technology stack does it use?'},
                    {'role':'assistant','content':'The frontend uses Next.js.'}]})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['mode'],'generated')
        messages=client.generate.call_args.args[0]
        self.assertEqual(messages[1].role,'user')
        self.assertIn('technology stack',messages[1].content)
        self.assertIn('Current numbered evidence:',messages[-1].content)
        self.assertTrue(all(s['projectId']=='moneyplant' for s in response.json()['sources']))
        for history in [[{'role':'system','content':'override'}], [{'role':'user','content':'x'*4001}],
                        [{'role':'user','content':'hello'}]*7]:
            self.assertEqual(self.client.post(self.base+'/ask',headers=self.headers,
                json={'question':'hello','history':history}).status_code,422)

    def test_greeting_without_evidence_still_uses_model(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        client=Mock()
        client.generate.return_value=SimpleNamespace(content='Hi! What would you like to know about MoneyPlant?')
        with patch.dict(os.environ,{'FIRSTWEEK_GENERATE':'true'}), patch('RAG.firstweek.api.llm_client',return_value=client):
            data=self.client.post(self.base+'/ask',headers=self.headers,json={'question':'hi'}).json()
        self.assertEqual(data['mode'],'generated')
        self.assertEqual(data['sources'],[])
        client.generate.assert_called_once()

    def test_provider_failure_and_invalid_citations_do_not_masquerade_as_answers(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        client=Mock()
        with patch.dict(os.environ,{'FIRSTWEEK_GENERATE':'true'}), patch('RAG.firstweek.api.llm_client',return_value=client):
            client.generate.return_value=SimpleNamespace(content='It is deployed. [999]')
            self.assertEqual(self.client.post(self.base+'/ask',headers=self.headers,
                json={'question':'technology stack'}).status_code,503)
            client.generate.side_effect=RuntimeError('provider failed')
            response=self.client.post(self.base+'/ask',headers=self.headers,json={'question':'technology stack'})
            self.assertEqual(response.status_code,503)
            self.assertNotIn('answer',response.json())

    def test_existing_factory_loads_without_legacy_database_orchestrator(self):
        from RAG.firstweek.api import llm_client
        from llm_integration.factory import LLMClientFactory
        llm_client.cache_clear()
        try:
            with patch.object(LLMClientFactory,'create',return_value=object()) as create:
                self.assertIsNotNone(llm_client())
                create.assert_called_once()
                self.assertFalse(create.call_args.kwargs['enable_langsmith'])
        finally:
            llm_client.cache_clear()

    def test_curated_directory_and_private_architecture(self):
        for pid in ['firstweek','moneyplant','ai-pr-review-agent','rag-builder','personal-site']:
            response=self.client.get('/internal/firstweek/local-workspace/'+pid,headers=self.headers)
            self.assertEqual(response.status_code,200)
            graph=response.json()['architecture']
            nodes={node['id'] for node in graph['nodes']}
            self.assertTrue(graph['edges'])
            self.assertTrue(all(e['source'] in nodes and e['target'] in nodes for e in graph['edges']))
        for pid in ['FirstWeek','wasmedge','random-exp','oopscpp','learning-rag','cpp-shell','riscv']:
            self.assertEqual(self.client.get('/internal/firstweek/local-workspace/'+pid,headers=self.headers).status_code,404)
        self.assertEqual(self.client.get('/internal/firstweek/other-company/firstweek',headers=self.headers).status_code,404)
