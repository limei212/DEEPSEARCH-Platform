import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.server import app
from app.management.store import ConfigStore


class APITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = ConfigStore(Path(self.temp.name)/'data',seed=False)
        patcher = patch('app.management.api.get_store',return_value=self.store)
        patcher.start();self.addCleanup(patcher.stop)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def test_draft_save_enable_and_restore_endpoints(self):
        config = {'name':'测试助手','description':'测试能力','system_prompt':'回答问题'}
        response = self.client.post('/api/manage/agents',json=config)
        self.assertEqual(response.status_code,200,response.text)
        draft = response.json()
        enabled = self.client.post('/api/manage/agents?publish=true',json=draft)
        self.assertEqual(enabled.status_code,200,enabled.text)
        self.assertEqual(enabled.json()['version'],1)
        conflict = self.client.post('/api/manage/agents',json=draft)
        self.assertEqual(conflict.status_code,409)
        versions = self.client.get('/api/manage/agents/'+draft['id']+'/versions').json()
        self.assertEqual(versions[0]['version'],1)

    def test_secret_is_not_returned_by_catalog(self):
        saved = self.client.post('/api/manage/resources',json={'kind':'knowledge','name':'内部知识库','config':{'url':'http://localhost:9380'},'secret':'only-a-fixture'}).json()
        self.assertTrue(saved['has_secret'])
        self.assertNotIn('only-a-fixture',self.client.get('/api/manage/catalog').text)

    def test_invalid_schema_and_unbound_resources_are_rejected(self):
        response = self.client.post('/api/manage/agents?publish=true',json={'name':'助手','description':'功能','system_prompt':'指令','output_format':'json','output_schema':{'type':'nonexistent'}})
        self.assertEqual(response.status_code,400)
        response = self.client.post('/api/manage/agents?publish=true',json={'name':'助手','description':'功能','system_prompt':'指令','knowledge':[{'resource_id':'missing','chat_ids':['x']}]})
        self.assertEqual(response.status_code,400)

    def test_skill_import_and_corrupt_zip(self):
        text='---\nname: evidence\ndescription: 证据分析\n---\n区分事实与推断。'
        response = self.client.post('/api/manage/skills/import',files={'file':('SKILL.md',text.encode(),'text/markdown')})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['status'],'ready')
        response = self.client.post('/api/manage/skills/import',files={'file':('broken.zip',b'broken','application/zip')})
        self.assertEqual(response.status_code,400)

    def test_upload_rejects_traversal_file_names_and_session_ids(self):
        response = self.client.post('/api/upload',data={'thread_id':'safe'},files={'files':('../outside.txt',b'test')})
        self.assertEqual(response.status_code,400)
        response = self.client.post('/api/upload',data={'thread_id':'../../outside'},files={'files':('safe.txt',b'test')})
        self.assertEqual(response.status_code,422)

    def test_management_requests_reject_foreign_browser_origins(self):
        payload={'kind':'knowledge','name':'测试连接','config':{'url':'http://localhost:9380'}}
        response=self.client.post('/api/manage/resources',json=payload,headers={'Origin':'https://untrusted.example'})
        self.assertEqual(response.status_code,403)
        response=self.client.post('/api/manage/resources',json=payload,headers={'Origin':'http://127.0.0.1:5173'})
        self.assertEqual(response.status_code,200)


if __name__ == '__main__':
    unittest.main()
