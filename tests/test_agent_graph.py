import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from app.management.models import AgentConfig
from app.management.runtime import run_single


class FixtureModel(BaseChatModel):
    tool_names: list[str] = []

    @property
    def _llm_type(self):
        return 'fixture'

    def bind_tools(self, tools, **kwargs):
        names = [tool.get('function',tool).get('name','') if isinstance(tool,dict) else tool.name for tool in tools]
        return self.model_copy(update={'tool_names':names})

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        structured = next((name for name in self.tool_names if name.startswith('response_format_')),None)
        message = AIMessage(content='',tool_calls=[{'id':'fixture-response','name':structured,'args':{'answer':'真实执行图已验证'}}]) if structured else AIMessage(content='真实执行图已验证')
        return ChatResult(generations=[ChatGeneration(message=message)])


class GraphTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_deepagents_graph_returns_valid_json_without_external_model(self):
        agent = AgentConfig(name='测试助手',description='验证执行图',system_prompt='请回答问题',output_format='json').model_dump()
        with tempfile.TemporaryDirectory() as folder, patch('app.management.runtime.model_for',return_value=FixtureModel()):
            result = await run_single(agent,{}, {'query':'测试'},Path(folder))
        self.assertEqual(result,{'answer':'真实执行图已验证'})


if __name__ == '__main__':
    unittest.main()
