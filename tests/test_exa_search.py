import importlib
import json
import os
import unittest
from unittest.mock import patch

import httpx

from app.management.models import AgentConfig
from app.management.runtime import runtime_status


class ExaSearchTests(unittest.TestCase):
    def test_search_agent_uses_exa_credentials(self):
        agent = AgentConfig(name='联网助手', description='检索公开资料', builtin_tools=['internet_search']).model_dump()
        agent['version'] = 1
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'configured-model-key', 'EXA_API_KEY': 'configured-search-key'}, clear=True):
            self.assertEqual(runtime_status(agent, {}), 'enabled')
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'configured-model-key', 'TAVILY_API_KEY': 'configured-old-key'}, clear=True):
            self.assertEqual(runtime_status(agent, {}), 'unconfigured')

    def invoke(self, handler, **arguments):
        module = importlib.import_module('app.tools.exa_tool')
        client = httpx.Client
        def create_client(**options):
            return client(transport=httpx.MockTransport(handler), **options)
        with patch.dict(os.environ, {'EXA_API_KEY': 'configured-search-key'}), patch.object(module.httpx, 'Client', side_effect=create_client):
            return module.internet_search.invoke({'query': '跨境电商趋势', **arguments})

    def test_search_preserves_sources_and_excerpts(self):
        def handler(request):
            self.assertEqual(str(request.url), 'https://api.exa.ai/search')
            self.assertEqual(request.method, 'POST')
            self.assertEqual(request.headers['x-api-key'], 'configured-search-key')
            self.assertEqual(json.loads(request.content), {'query': '跨境电商趋势', 'type': 'auto', 'numResults': 5, 'contents': {'highlights': True}})
            return httpx.Response(200, json={'requestId': 'search-1', 'results': [{'title': '趋势报告', 'url': 'https://example.com/report', 'publishedDate': '2026-10-01T00:00:00Z', 'author': '研究团队', 'highlights': ['有来源的内容摘要'], 'id': 'https://example.com/report'}]})
        result = self.invoke(handler)
        self.assertEqual(result['provider'], 'exa')
        self.assertEqual(result['results'][0]['url'], 'https://example.com/report')
        self.assertEqual(result['results'][0]['content'], '有来源的内容摘要')
        self.assertEqual(result['results'][0]['published_date'], '2026-10-01T00:00:00Z')

    def test_news_and_full_text_options(self):
        def handler(request):
            body = json.loads(request.content)
            self.assertEqual(body['category'], 'news')
            self.assertEqual(body['numResults'], 3)
            self.assertEqual(body['contents']['text'], {'maxCharacters': 12000})
            return httpx.Response(200, json={'results': [{'title': '新闻', 'url': 'https://example.com/news', 'text': '网页正文', 'highlights': ['关键段落']}]})
        result = self.invoke(handler, topic='news', max_results=3, include_raw_content=True)
        self.assertEqual(result['results'][0]['raw_content'], '网页正文')

    def test_missing_key_and_invalid_inputs_do_not_send_requests(self):
        module = importlib.import_module('app.tools.exa_tool')
        with patch.dict(os.environ, {'EXA_API_KEY': ''}), patch.object(module.httpx, 'Client', side_effect=AssertionError('Unexpected network request')):
            with self.assertRaisesRegex(ValueError, 'EXA_API_KEY'):
                module.internet_search.invoke({'query': 'research'})
        def unexpected_request(request):
            self.fail('Invalid input must not make a network request')
        for arguments in [{'query': ' '}, {'max_results': 0}, {'max_results': 21}]:
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                self.invoke(unexpected_request, **arguments)

    def test_service_errors_and_timeouts_do_not_leak_key(self):
        for code in [401, 402, 429, 503]:
            with self.subTest(code=code), self.assertRaises(ValueError) as caught:
                self.invoke(lambda request: httpx.Response(code, json={'error': 'configured-search-key'}))
            self.assertNotIn('configured-search-key', str(caught.exception))
        def timeout(request):
            raise httpx.ReadTimeout('configured-search-key', request=request)
        with self.assertRaisesRegex(ValueError, '超时') as caught:
            self.invoke(timeout)
        self.assertNotIn('configured-search-key', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
