import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from typing import ClassVar

from fastapi.testclient import TestClient
from app.api.server import app
from app.management.models import AgentConfig
from app.management.store import ConfigStore
from app.management.runtime import builtin_tools, run_single
from app.rag.session import current_index
from tests.test_agent_graph import FixtureModel


class RecordingModel(FixtureModel):
    recorded: ClassVar[list] = []

    def _get_ls_params(self, **kwargs):
        return {**super()._get_ls_params(**kwargs),'ls_provider':'openai'}

    def bind_tools(self, tools, **kwargs):
        self.recorded.append([tool.name if hasattr(tool, 'name') else tool.get('function',tool).get('name','') for tool in tools])
        return super().bind_tools(tools, **kwargs)


class DocumentIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_document_graph_cannot_bypass_retrieval_with_binary_file_reader(self):
        RecordingModel.recorded.clear()
        agent=AgentConfig(name='文档检索助手',description='检索附件',builtin_tools=['search_task_documents']).model_dump()
        with tempfile.TemporaryDirectory() as folder,patch('app.management.runtime.model_for',return_value=RecordingModel()):
            await run_single(agent,{},'检索附件',Path(folder))
        names=set(name for call in RecordingModel.recorded for name in call)
        self.assertIn('search_task_documents',names)
        self.assertNotIn('read_file',names)

    async def test_native_tool_is_registered(self):
        self.assertIn('search_task_documents',builtin_tools())

    async def test_default_agents_use_document_search_without_ragflow_resource(self):
        with tempfile.TemporaryDirectory() as folder:
            store=ConfigStore(Path(folder))
            doc=next((a for a in store.list_agents() if a['name']=='文档检索助手'),None)
            self.assertIsNotNone(doc)
            self.assertEqual(doc['knowledge'],[])
            self.assertEqual(doc['builtin_tools'],['search_task_documents'])
            self.assertFalse(any(r['id']=='ragflow-default' for r in store.list_resources()))

    async def test_existing_default_is_migrated_once_preserving_old_versions(self):
        with tempfile.TemporaryDirectory() as folder:
            store=ConfigStore(Path(folder),seed=False)
            old=store.save_agent(AgentConfig(id='builtin-ragflow',name='RAGFlow助手',description='内部知识库',system_prompt='旧提示词',knowledge=[{'resource_id':'ragflow-default','chat_ids':[]}]),publish=True,validate=False)
            migrated=ConfigStore(Path(folder))
            agent=migrated.get_agent(old['id'])
            self.assertEqual(agent['name'],'文档检索助手')
            self.assertEqual(agent['knowledge'],[])
            self.assertEqual(agent['version'],2)
            with migrated.connect() as db:
                saved=json.loads(db.execute('SELECT config FROM versions WHERE agent_id=? AND version=1',(old['id'],)).fetchone()[0])
                self.assertEqual(saved['system_prompt'],'旧提示词')
            self.assertEqual(ConfigStore(Path(folder)).get_agent(old['id'])['version'],2)

    async def test_single_agent_owns_and_releases_scope_without_external_calls(self):
        scopes=[]
        def model(agent):scopes.append(current_index.get());return FixtureModel()
        agent=AgentConfig(name='检索助手',description='文档检索',builtin_tools=['search_task_documents']).model_dump()
        with tempfile.TemporaryDirectory() as folder,patch('app.management.runtime.model_for',side_effect=model):
            await run_single(agent,{},'问题',Path(folder))
        self.assertIsNotNone(scopes[0])
        self.assertTrue(scopes[0].closed.is_set())
        self.assertIsNone(current_index.get())

    async def test_upload_list_survives_page_refresh(self):
        with TestClient(app) as client:
            identifier='document-list-test'
            response=client.post('/api/upload',data={'thread_id':identifier},files={'files':('test.md',b'fixture document','text/markdown')})
            self.assertEqual(response.status_code,200)
            files=client.get('/api/uploads/'+identifier)
            self.assertEqual(files.status_code,200)
            self.assertEqual(files.json()['files'][0]['name'],'test.md')
            self.assertNotIn('path',files.json()['files'][0])

if __name__=='__main__':unittest.main()
