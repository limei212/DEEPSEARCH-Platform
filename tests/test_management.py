import json
import tempfile
import unittest
from pathlib import Path

from app.management.models import AgentConfig, ResourceConfig
from app.management.store import ConfigStore, ConflictError


class ConfigStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = ConfigStore(Path(self.temp.name), seed=False)

    def agent(self, **changes):
        return AgentConfig(name='策略助手', description='分析品类策略', system_prompt='先找依据，再给建议', **changes)

    def test_draft_is_not_dispatched_and_published_snapshot_is_immutable(self):
        draft = self.store.save_agent(self.agent())
        self.assertEqual(self.store.snapshot()['agents'], [])
        published = self.store.save_agent(AgentConfig(**draft), publish=True)
        snapshot = self.store.snapshot()
        changed = dict(published, system_prompt='新提示词')
        self.store.save_agent(AgentConfig(**changed))
        self.assertEqual(self.store.snapshot()['agents'][0]['system_prompt'], '先找依据，再给建议')
        self.assertEqual(snapshot['agents'][0]['version'], 1)

    def test_stale_save_is_rejected(self):
        saved = self.store.save_agent(self.agent())
        self.store.save_agent(AgentConfig(**saved))
        with self.assertRaises(ConflictError):
            self.store.save_agent(AgentConfig(**saved))

    def test_restore_creates_a_draft_and_preserves_active_version(self):
        first = self.store.save_agent(self.agent(), publish=True)
        self.store.save_agent(AgentConfig(**dict(first, system_prompt='第二版')), publish=True)
        restored = self.store.restore_agent(first['id'], 1)
        self.assertEqual(restored['system_prompt'], '先找依据，再给建议')
        self.assertEqual(self.store.snapshot()['agents'][0]['system_prompt'], '第二版')

    def test_resource_secret_is_encrypted_masked_and_preserved_on_edit(self):
        resource = self.store.save_resource(ResourceConfig(kind='knowledge', name='公司知识库', config={'url':'http://localhost:9380'}, secret='test-private-key'))
        self.assertTrue(resource['has_secret'])
        self.assertNotIn('test-private-key', json.dumps(resource))
        updated = self.store.save_resource(ResourceConfig(**dict(resource, name='更名后知识库')))
        self.assertEqual(self.store.get_resource(updated['id'], private=True)['secret'], 'test-private-key')
        self.assertNotIn(b'test-private-key', (Path(self.temp.name) / 'config.sqlite3').read_bytes())

    def test_unavailable_bound_resource_blocks_publish(self):
        with self.assertRaisesRegex(ValueError, '资源'):
            self.store.save_agent(self.agent(skill_ids=['missing']), publish=True)

    def test_disabled_agent_is_not_in_snapshot(self):
        published = self.store.save_agent(self.agent(), publish=True)
        self.store.disable_agent(published['id'])
        self.assertEqual(self.store.snapshot()['agents'], [])

    def test_resource_change_invalidates_discovered_tools(self):
        resource = self.store.save_resource(ResourceConfig(kind='mcp', name='工具服务', config={'transport':'http','url':'http://localhost:9001/mcp'}))
        self.store.record_probe(resource['id'], {'status':'ready','message':'连接成功','tools':[{'name':'search'}]})
        edited = self.store.save_resource(ResourceConfig(**dict(self.store.get_resource(resource['id']), config={'transport':'http','url':'http://localhost:9002/mcp'})))
        self.assertEqual(edited['status'], 'unconfigured')
        self.assertEqual(edited['discovery'], {})


if __name__ == '__main__':
    unittest.main()
