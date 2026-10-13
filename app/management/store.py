import copy
import json
import os
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from cryptography.fernet import Fernet

from .models import AgentConfig, ResourceConfig, BUILTIN_TOOLS


class ConflictError(ValueError):
    pass


class ConfigStore:
    def __init__(self, directory: Path, *, seed=True):
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        key_path = directory / 'secrets.key'
        if not key_path.exists():
            try:
                with key_path.open('xb') as handle:
                    handle.write(Fernet.generate_key())
                key_path.chmod(0o600)
            except FileExistsError:
                pass
        self.cipher = Fernet(key_path.read_bytes())
        self.path = directory / 'config.sqlite3'
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS agents(id TEXT PRIMARY KEY, revision INTEGER, draft TEXT, published TEXT, enabled INTEGER DEFAULT 0);
                CREATE TABLE IF NOT EXISTS versions(agent_id TEXT, version INTEGER, config TEXT, created_at TEXT, PRIMARY KEY(agent_id,version));
                CREATE TABLE IF NOT EXISTS resources(id TEXT PRIMARY KEY, revision INTEGER, body TEXT, secret BLOB);
            ''')
        if seed:
            self.seed()

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def seed(self):
        from app.agent.prompts import sub_agents_content
        with self.connect() as db:
            if db.execute('SELECT count(*) FROM agents').fetchone()[0]:
                return
        resource = self.save_resource(ResourceConfig(id='ragflow-default', kind='knowledge', name='RAGFlow 默认连接', config={
            'url':os.getenv('RAGFLOW_API_URL', 'http://127.0.0.1:9380'), 'secret_env':'RAGFLOW_API_KEY',
        }))
        defaults = [('tavily','research',['internet_search']), ('db','database',['list_sql_tables','get_table_data','execute_sql_query']), ('ragflow','knowledge',[])]
        for key, icon, tools in defaults:
            data = sub_agents_content[key]
            config = AgentConfig(id=f'builtin-{key}', name=data['name'], description=data['description'], system_prompt=data['system_prompt'], icon=icon, builtin_tools=tools,
                knowledge=[{'resource_id':resource['id'],'chat_ids':[]}] if key == 'ragflow' else [])
            self.save_agent(config, publish=True, validate=False)

    def save_agent(self, config: AgentConfig, *, publish=False, validate=True):
        body = config.model_dump()
        if publish and validate:
            self.validate_agent(body)
        identifier = config.id or str(uuid.uuid4())
        with self.lock, self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT * FROM agents WHERE id=?', (identifier,)).fetchone()
            if old and old['revision'] != config.revision:
                raise ConflictError('配置已更新，请重新载入后再保存')
            if not old and config.revision:
                raise ConflictError('助手已不存在，请重新载入')
            revision = (old['revision'] if old else 0) + 1
            version = json.loads(old['published'])['version'] if old and old['published'] else 0
            body.update(id=identifier, revision=revision)
            published = old['published'] if old else None
            enabled = old['enabled'] if old else 0
            if publish:
                version += 1
                active = dict(body, version=version)
                published = json.dumps(active, ensure_ascii=False)
                enabled = 1
                db.execute('INSERT INTO versions VALUES (?,?,?,?)', (identifier,version,published,datetime.now(timezone.utc).isoformat()))
            db.execute('INSERT OR REPLACE INTO agents VALUES (?,?,?,?,?)', (identifier,revision,json.dumps(body,ensure_ascii=False),published,enabled))
        return self.get_agent(identifier)

    def validate_agent(self, body):
        from .contracts import validate_config
        validate_config(body)
        for binding in body['knowledge']:
            resource = self.get_resource(binding['resource_id'])
            if resource['kind'] != 'knowledge' or resource['status'] != 'ready':
                raise ValueError('知识库资源尚未连接成功，请先测试连接')
            available = {item['id'] for item in resource['discovery'].get('chats', [])}
            if not binding['chat_ids'] or not set(binding['chat_ids']) <= available:
                raise ValueError('请选择有效的 RAGFlow 聊天助手')
        for identifier in body['skill_ids']:
            resource = self.get_resource(identifier)
            if resource['kind'] != 'skill' or resource['status'] != 'ready':
                raise ValueError('Skill 资源尚未完成配置')
            available_tools = set(body['builtin_tools']) | {name for item in body['mcp'] for name in item['tools']}
            missing = set(resource['config'].get('required_tools', [])) - available_tools
            if missing:
                raise ValueError('Skill 缺少工具：' + '、'.join(sorted(missing)))
        for binding in body['mcp']:
            resource = self.get_resource(binding['resource_id'])
            available = {item['name'] for item in resource['discovery'].get('tools', [])}
            if resource['kind'] != 'mcp' or resource['status'] != 'ready' or not binding['tools'] or not set(binding['tools']) <= available:
                raise ValueError('MCP 资源未连接或勾选工具已失效，请重新测试连接')

    def get_agent(self, identifier):
        with self.connect() as db:
            row = db.execute('SELECT * FROM agents WHERE id=?', (identifier,)).fetchone()
        if not row:
            raise ValueError('助手不存在')
        body = json.loads(row['draft'])
        active = json.loads(row['published']) if row['published'] else None
        body.update(enabled=bool(row['enabled']), version=active['version'] if active else 0,
            has_changes=bool(active and AgentConfig(**active).model_dump(exclude={'revision'}) != AgentConfig(**body).model_dump(exclude={'revision'})))
        return body

    def list_agents(self):
        with self.connect() as db:
            ids = [row[0] for row in db.execute('SELECT id FROM agents ORDER BY rowid')]
        return [self.get_agent(identifier) for identifier in ids]

    def disable_agent(self, identifier):
        with self.lock, self.connect() as db:
            changed = db.execute('UPDATE agents SET enabled=0, revision=revision+1 WHERE id=?', (identifier,)).rowcount
            if not changed:
                raise ValueError('助手不存在')
            row = db.execute('SELECT draft,revision FROM agents WHERE id=?',(identifier,)).fetchone()
            body = json.loads(row['draft']); body['revision'] = row['revision']
            db.execute('UPDATE agents SET draft=? WHERE id=?',(json.dumps(body,ensure_ascii=False),identifier))
        return self.get_agent(identifier)

    def versions(self, identifier):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT version,created_at FROM versions WHERE agent_id=? ORDER BY version DESC',(identifier,))]

    def restore_agent(self, identifier, version):
        with self.connect() as db:
            row = db.execute('SELECT config FROM versions WHERE agent_id=? AND version=?',(identifier,version)).fetchone()
        if not row:
            raise ValueError('版本不存在')
        body = json.loads(row['config']); body['revision'] = self.get_agent(identifier)['revision']
        return self.save_agent(AgentConfig(**body))

    def save_resource(self, config: ResourceConfig):
        from .connectors import validate_resource
        body = config.model_dump(exclude={'secret','clear_secret'})
        validate_resource(body)
        identifier = config.id or str(uuid.uuid4())
        with self.lock, self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT * FROM resources WHERE id=?',(identifier,)).fetchone()
            if old and old['revision'] != config.revision:
                raise ConflictError('资源已更新，请重新载入后再保存')
            previous = json.loads(old['body']) if old else None
            if previous and previous['kind'] != config.kind:
                raise ValueError('不能改变已有资源的类型，请新增资源')
            changed = not previous or previous['config'] != body['config'] or config.secret is not None or config.clear_secret
            secret = self.cipher.encrypt(config.secret.encode()) if config.secret else (old['secret'] if old else None)
            if config.clear_secret:
                secret = None
                body['config'].pop('secret_env', None)
            body.update(id=identifier,revision=(old['revision'] if old else 0)+1,
                status='ready' if config.kind == 'skill' else (previous['status'] if previous and not changed else 'unconfigured'),
                discovery=previous['discovery'] if previous and not changed else {},
                message='技能已保存' if config.kind == 'skill' else (previous.get('message','') if previous and not changed else '尚未测试连接'))
            db.execute('INSERT OR REPLACE INTO resources VALUES (?,?,?,?)',(identifier,body['revision'],json.dumps(body,ensure_ascii=False),secret))
        return self.get_resource(identifier)

    def get_resource(self, identifier, *, private=False):
        with self.connect() as db:
            row = db.execute('SELECT * FROM resources WHERE id=?',(identifier,)).fetchone()
        if not row:
            raise ValueError('资源不存在')
        body = json.loads(row['body']); body['has_secret'] = bool(row['secret'] or body['config'].get('secret_env'))
        if private:
            body['secret'] = self.cipher.decrypt(row['secret']).decode() if row['secret'] else os.getenv(body['config'].get('secret_env',''), '')
        return body

    def list_resources(self):
        with self.connect() as db:
            ids = [row[0] for row in db.execute('SELECT id FROM resources ORDER BY rowid')]
        return [self.get_resource(identifier) for identifier in ids]

    def record_probe(self, identifier, probe, *, revision=None):
        with self.lock, self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT body FROM resources WHERE id=?',(identifier,)).fetchone()
            if not row:
                raise ValueError('资源不存在')
            body = json.loads(row['body'])
            if revision is not None and body['revision'] != revision:
                raise ConflictError('连接测试期间资源已修改，请重新测试')
            body.update(status=probe['status'],message=probe['message'],discovery={key:value for key,value in probe.items() if key not in ('status','message')})
            db.execute('UPDATE resources SET body=? WHERE id=?',(json.dumps(body,ensure_ascii=False),identifier))
        return self.get_resource(identifier)

    def snapshot(self):
        with self.lock, self.connect() as db:
            agents = [json.loads(row[0]) for row in db.execute('SELECT published FROM agents WHERE enabled=1 AND published IS NOT NULL')]
            ids = {binding['resource_id'] for agent in agents for binding in agent['knowledge']+agent['mcp']} | {identifier for agent in agents for identifier in agent['skill_ids']}
            resources = {identifier:self.get_resource(identifier,private=True) for identifier in ids}
        return copy.deepcopy({'agents':agents,'resources':resources})


_store = None
_store_lock = threading.Lock()

def get_store():
    global _store
    with _store_lock:
        if _store is None:
            _store = ConfigStore(Path(os.getenv('DEEPSEARCH_DATA_DIR', str(Path(__file__).resolve().parents[2] / '.agent-data'))))
    return _store
