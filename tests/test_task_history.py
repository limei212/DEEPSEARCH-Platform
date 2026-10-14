import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.api.task_store import TaskStore


def event(name, data=None):
    return {'type':'monitor_event','event':name,'message':name,'data':data or {},'timestamp':'2026-10-14T12:00:00'}

class TaskHistoryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.store = TaskStore(self.root/'data', output_root=self.root/'output')

    def test_reopening_database_restores_question_answer_and_all_events(self):
        self.store.create('task-1','workspace-1','请查询公司白皮书中的品类策略')
        for index in range(150):
            self.store.append('task-1',event('tool_start',{'index':index}))
        self.store.append('task-1',event('task_result',{'result':'保留完整答案'}))
        reopened = TaskStore(self.root/'data', output_root=self.root/'output')
        task = reopened.get('task-1')
        self.assertEqual(task['result'],'保留完整答案')
        self.assertEqual(len(task['events']),151)
        self.assertEqual(task['content'],'请查询公司白皮书中的品类策略')
        self.assertEqual(task['title'],'请查询公司白皮书')
        self.assertFalse(task['isRunning'])

    def test_pagination_reaches_every_task_once(self):
        for index in range(123):
            self.store.create(f'task-{index}','workspace',f'任务 {index}')
        found=[]; cursor=None
        while True:
            page=self.store.list(before=cursor,limit=50)
            found.extend(task['id'] for task in page['tasks'])
            cursor=page['next_cursor']
            if cursor is None: break
        self.assertEqual(len(found),123)
        self.assertEqual(len(set(found)),123)
        self.assertEqual(found[0],'task-122')
        self.assertEqual(found[-1],'task-0')

    def test_multiple_turns_in_one_workspace_remain_separate(self):
        self.store.create('first','chat','第一轮')
        self.store.append('first',event('task_result',{'result':'第一轮答案'}))
        self.store.create('second','chat','第二轮')
        self.store.append('second',event('error',{'reason':'failed'}))
        tasks=self.store.workspace('chat')
        self.assertEqual([task['id'] for task in tasks],['first','second'])
        self.assertEqual(tasks[0]['result'],'第一轮答案')
        self.assertEqual(tasks[1]['status'],'failed')

    def test_restart_marks_unfinished_tasks_interrupted_without_losing_events(self):
        self.store.create('running','chat','未完成任务')
        self.store.append('running',event('tool_start'))
        self.store.create('cancelled','other','取消任务')
        self.store.append('cancelled',event('task_cancelled'))
        self.store.recover_interrupted()
        task=self.store.get('running')
        self.assertEqual(task['status'],'interrupted')
        self.assertFalse(task['isRunning'])
        self.assertEqual(task['events'][0]['event'],'tool_start')
        self.assertEqual(self.store.get('cancelled')['status'],'cancelled')

    def test_saved_file_entries_and_credentials_are_safe(self):
        folder=self.root/'output/session-test'
        folder.mkdir(parents=True)
        (folder/'report.md').write_text('report',encoding='utf-8')
        self.store.create('files','chat','文件测试')
        self.store.append('files',event('session_created',{'path':str(folder)}))
        with patch.dict(os.environ,{'EXA_API_KEY':'fixture-private-credential'}):
            self.store.append('files',event('error',{'reason':'fixture-private-credential'}))
        task=self.store.get('files')
        self.assertEqual(task['files'][0]['name'],'report.md')
        self.assertNotIn('fixture-private-credential',str(task))

if __name__=='__main__': unittest.main()
