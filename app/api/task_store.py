"""本地任务历史：问题、全部执行事件、答案和交付文件入口。"""
import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path

current_task_id = ContextVar('persisted_task_id', default=None)

def clean(value):
    text = json.dumps(value, ensure_ascii=False, default=str)
    for name, secret in os.environ.items():
        if name.endswith('_API_KEY') and len(secret) >= 8:
            text = text.replace(secret, '[REDACTED]')
    return json.loads(text)

class TaskStore:
    def __init__(self, directory: Path, *, output_root=None):
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory/'tasks.sqlite3'
        self.output_root = Path(output_root or Path(__file__).resolve().parents[2]/'app/output').resolve()
        self.lock = threading.RLock()
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS tasks(
                    ordinal INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL,
                    workspace TEXT NOT NULL, query TEXT NOT NULL, created_at TEXT NOT NULL,
                    status TEXT NOT NULL, result TEXT NOT NULL DEFAULT '', session_path TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS task_events(
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL, body TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS task_workspace ON tasks(workspace, ordinal);
                CREATE INDEX IF NOT EXISTS task_event_index ON task_events(task_id, sequence);
            ''')

    @contextmanager
    def connect(self):
        with self.lock:
            db = sqlite3.connect(self.path, timeout=15)
            db.row_factory = sqlite3.Row
            try:
                with db: yield db
            finally: db.close()

    def create(self, identifier, workspace, query):
        try:
            with self.connect() as db:
                db.execute('INSERT INTO tasks(id,workspace,query,created_at,status) VALUES(?,?,?,?,?)',
                           (identifier, workspace, clean(query), datetime.now(timezone.utc).isoformat(), 'running'))
        except sqlite3.IntegrityError as error:
            raise ValueError('任务已存在，不能重复提交') from error

    def append(self, identifier, payload):
        payload = clean(payload)
        with self.connect() as db:
            row = db.execute('SELECT status FROM tasks WHERE id=?', (identifier,)).fetchone()
            if row is None: return payload
            cursor = db.execute('INSERT INTO task_events(task_id,body) VALUES(?,?)', (identifier, json.dumps(payload,ensure_ascii=False)))
            payload.update(task_id=identifier, sequence=cursor.lastrowid)
            name = payload['event']; data = payload.get('data') or {}
            if name == 'session_created':
                db.execute('UPDATE tasks SET session_path=? WHERE id=?',(data.get('path',''),identifier))
            elif name == 'task_result':
                result = data.get('result') or payload['message']
                db.execute('UPDATE tasks SET status=?,result=? WHERE id=?',('completed',result if isinstance(result,str) else json.dumps(result,ensure_ascii=False),identifier))
            elif name in ('error','task_cancelled','task_interrupted') and row['status'] == 'running':
                status = {'error':'failed','task_cancelled':'cancelled','task_interrupted':'interrupted'}[name]
                db.execute('UPDATE tasks SET status=?,result=? WHERE id=?',(status,payload['message'],identifier))
        return payload

    def recover_interrupted(self):
        with self.connect() as db:
            identifiers = [row[0] for row in db.execute("SELECT id FROM tasks WHERE status='running'")]
        for identifier in identifiers:
            self.append(identifier, {'type':'monitor_event','event':'task_interrupted','message':'服务已重启，此任务已中断；此前记录已保留，可重新提交任务。','data':{},'timestamp':datetime.now(timezone.utc).isoformat()})

    def metadata(self, row):
        return {'id':row['id'],'workspaceId':row['workspace'],'content':row['query'],
                'title':' '.join(row['query'].split()),'timestamp':row['created_at'],'status':row['status']}

    def list(self, *, before=None, limit=50):
        with self.connect() as db:
            rows = db.execute('SELECT * FROM tasks WHERE ordinal<? ORDER BY ordinal DESC LIMIT ?',
                              (before if before is not None else 9223372036854775807, limit+1)).fetchall()
        return {'tasks':[self.metadata(row) for row in rows[:limit]],
                'next_cursor':rows[limit-1]['ordinal'] if len(rows)>limit else None}

    def files(self, path):
        folder = Path(path).resolve() if path else None
        if folder is None or not folder.is_relative_to(self.output_root) or not folder.is_dir(): return []
        files = []
        for file in folder.rglob('*'):
            if file.is_file() and file.resolve().is_relative_to(self.output_root):
                stat = file.stat()
                files.append({'name':file.name,'type':'file','path':str(file),'size':stat.st_size,'mtime':stat.st_mtime})
        return sorted(files,key=lambda item:item['mtime'],reverse=True)

    def get(self, identifier):
        with self.connect() as db:
            row = db.execute('SELECT * FROM tasks WHERE id=?',(identifier,)).fetchone()
            if row is None: raise KeyError(identifier)
            events = [dict(json.loads(event['body']),task_id=identifier,sequence=event['sequence'])
                      for event in db.execute('SELECT sequence,body FROM task_events WHERE task_id=? ORDER BY sequence',(identifier,))]
        return dict(self.metadata(row),events=events,result=row['result'],isRunning=row['status']=='running',
                    sessionPath=row['session_path'],files=self.files(row['session_path']))

    def workspace(self, identifier):
        with self.connect() as db:
            ids = [row[0] for row in db.execute('SELECT id FROM tasks WHERE workspace=? ORDER BY ordinal',(identifier,))]
        return [self.get(identifier) for identifier in ids]

_store = None
_lock = threading.Lock()
def get_task_store():
    global _store
    with _lock:
        if _store is None:
            _store = TaskStore(Path(os.getenv('DEEPSEARCH_DATA_DIR',str(Path(__file__).resolve().parents[2]/'.agent-data'))))
    return _store
