import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from langchain_core.messages import AIMessage, HumanMessage

from app.management.models import AgentConfig
from app.management.connectors import probe_resource
from app.management.runtime import build_main_agent, connected_tools, run_single


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_mcp_discovers_tools_and_only_selected_tool_is_callable(self):
        resource = {'id':'fixture','kind':'mcp','name':'Echo','secret':'','config':{'transport':'stdio','command':sys.executable,'args':[str(Path(__file__).parent / 'fixtures/mcp_echo.py')]}}
        probe = await probe_resource(resource)
        self.assertEqual(probe['status'],'ready',probe)
        self.assertEqual({tool['name'] for tool in probe['tools']},{'echo','unselected'})
        agent = AgentConfig(name='test',description='test',mcp=[{'resource_id':'fixture','tools':['echo']}]).model_dump()
        async with connected_tools(agent,{'fixture':resource}) as tools:
            self.assertEqual(len(tools),1)
            self.assertIn('echo',tools[0].name)
            result = await tools[0].ainvoke({'message':'hello'})
            self.assertIn('echo: hello',result)

    async def test_draft_execution_uses_exact_prompt_and_validates_json(self):
        config = AgentConfig(name='test',description='test',system_prompt='研究：{{query}}',output_format='json').model_dump()
        fake_graph = AsyncMock()
        fake_graph.ainvoke.return_value = {'structured_response':{'answer':'verified'},'messages':[AIMessage(content='verified')]}
        with tempfile.TemporaryDirectory() as directory, patch('app.management.runtime.model_for',return_value='mock-model'), patch('app.management.runtime.create_deep_agent',return_value=fake_graph) as factory:
            result = await run_single(config,{}, {'query':'品类策略'},Path(directory))
            self.assertEqual(result,{'answer':'verified'})
            self.assertIn('研究：品类策略',factory.call_args.kwargs['system_prompt'])
            self.assertEqual(factory.call_args.kwargs['response_format'],config['output_schema'])

    async def test_main_registers_published_agent_with_compiled_input_contract(self):
        agent = dict(AgentConfig(id='configured-agent',name='策略助手',description='品类分析',system_prompt='已启用提示词').model_dump(),version=2)
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'OPENAI_API_KEY':'fixture-model-key'}), patch('app.management.runtime.model_for',return_value='mock-model'), patch('app.management.runtime.create_deep_agent',return_value='main-graph') as factory:
            build_main_agent({'agents':[agent],'resources':{}},Path(directory))
            registered = factory.call_args.kwargs['subagents']
            self.assertEqual(registered[0]['name'],'configured-agent')
            self.assertIn('品类分析',registered[0]['description'])
            with patch('app.management.runtime.run_single',new_callable=AsyncMock,return_value='策略结果') as execute:
                result = await registered[0]['runnable'].ainvoke({'messages':[HumanMessage(content='{"query":"选品"}')]})
                self.assertEqual(result['messages'][-1].text,'策略结果')
                self.assertEqual(execute.call_args.args[0]['system_prompt'],'已启用提示词')


if __name__ == '__main__':
    unittest.main()
