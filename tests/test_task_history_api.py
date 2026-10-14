import tempfile
import asyncio
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from app.api.server import app
from app.api.server import finish_persisted
from app.api.monitor import monitor
from app.api.task_store import TaskStore

class TaskHistoryAPITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store=TaskStore(Path(self.temp.name))
        for module in ['app.api.server','app.api.monitor']:
            patcher=patch(module+'.get_task_store',return_value=self.store)
            patcher.start();self.addCleanup(patcher.stop)
        patcher=patch('app.api.server.get_store',return_value=SimpleNamespace(snapshot=lambda:{'agents':[],'resources':{}}))
        patcher.start();self.addCleanup(patcher.stop)

    def test_task_endpoint_saves_actual_events_before_websocket_delivery(self):
        async def execute(query,identifier,snapshot):
            monitor._emit('tool_start','开始工具',{'tool_name':'fixture'})
            monitor.report_task_result('真实接口路径中的测试答案')
        with patch('app.api.server.run_deep_agent',execute),TestClient(app) as client:
            with client.websocket_connect('/ws/chat') as socket:
                self.assertEqual(socket.receive_json()['type'],'history')
                response=client.post('/api/task',json={'query':'保存这条任务','thread_id':'chat','task_id':'task-test'})
                self.assertEqual(response.status_code,200)
                self.assertEqual(socket.receive_json()['task_id'],'task-test')
                final=socket.receive_json()
                self.assertEqual(final['event'],'task_result')
                detail=client.get('/api/tasks/task-test').json()
                self.assertEqual(detail['result'],'真实接口路径中的测试答案')
                self.assertEqual(detail['events'][-1]['sequence'],final['sequence'])
                self.assertEqual(client.get('/api/tasks').json()['tasks'][0]['id'],'task-test')
        reopened=TaskStore(Path(self.temp.name))
        self.assertEqual(reopened.get('task-test')['status'],'completed')

    def test_reconnecting_replays_complete_saved_conversation(self):
        self.store.create('previous','chat','原来的问题')
        self.store.append('previous',{'type':'monitor_event','event':'task_result','message':'完成','data':{'result':'原来的答案'},'timestamp':'2026-10-14T12:00:00'})
        with TestClient(app) as client:
            with client.websocket_connect('/ws/chat') as socket:
                restored=socket.receive_json()
                self.assertEqual(restored['tasks'][0]['result'],'原来的答案')
                self.assertEqual(restored['tasks'][0]['events'][0]['task_id'],'previous')
                self.assertFalse(restored['tasks'][0]['isRunning'])

    def test_duplicate_submission_and_invalid_history_cursor_are_rejected(self):
        self.store.create('duplicate','chat','先前任务')
        with TestClient(app) as client:
            response=client.post('/api/task',json={'query':'重复提交','thread_id':'chat','task_id':'duplicate'})
            self.assertEqual(response.status_code,409)
            self.assertEqual(client.get('/api/tasks?limit=10000').status_code,422)
            self.assertEqual(client.get('/api/tasks/missing').status_code,404)

    def test_cancelled_before_execution_is_saved(self):
        self.store.create('not-started','chat','刚提交的任务')
        async def cancel_immediately():
            task=asyncio.create_task(asyncio.sleep(60))
            task.cancel()
            try: await task
            except asyncio.CancelledError: pass
            finish_persisted('chat','not-started',task)
        asyncio.run(cancel_immediately())
        self.assertEqual(self.store.get('not-started')['status'],'cancelled')

if __name__=='__main__':unittest.main()
