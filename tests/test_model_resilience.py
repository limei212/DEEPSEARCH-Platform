import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from langchain.chat_models import init_chat_model
from openai import APIStatusError

from app.management.runtime import model_for


class ModelResilienceTests(unittest.IsolatedAsyncioTestCase):
    async def invoke_fixture(self, statuses):
        self.calls=0

        def respond(request):
            status=statuses[min(self.calls,len(statuses)-1)]
            self.calls+=1
            if status!=200:
                return httpx.Response(status,headers={'retry-after-ms':'1','x-request-id':'fixture-busy-request'},json={'error':{'message':'Service is too busy','type':'service_unavailable_error'}})
            return httpx.Response(200,json={'id':'fixture-completion','model':'fixture-model','object':'chat.completion','choices':[{'index':0,'message':{'role':'assistant','content':'模型恢复正常'},'finish_reason':'stop'}]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            def factory(**kwargs):
                return init_chat_model(**kwargs,http_async_client=client)
            with patch.dict(os.environ,{'OPENAI_API_KEY':'fixture-model-key','OPENAI_BASE_URL':'https://fixture.invalid/v1','LLM_QWEN_MAX':'fixture-model'}),patch('app.management.runtime.init_chat_model',side_effect=factory):
                return await model_for({}).ainvoke('fixture only')

    async def test_model_recovers_after_two_busy_responses_without_replaying_agent(self):
        result=await self.invoke_fixture([503,503,200])
        self.assertEqual(result.content,'模型恢复正常')
        self.assertEqual(self.calls,3)

    async def test_persistent_busy_service_stops_after_four_retries(self):
        with self.assertRaises(APIStatusError):
            await self.invoke_fixture([503])
        self.assertEqual(self.calls,5)

    async def test_invalid_key_is_not_retried(self):
        with self.assertRaises(APIStatusError):
            await self.invoke_fixture([401])
        self.assertEqual(self.calls,1)

    async def test_busy_error_is_readable_and_keeps_request_identifier(self):
        from app.management.runtime import model_error_message
        request=httpx.Request('POST','https://fixture.invalid/v1/chat/completions')
        response=httpx.Response(503,request=request,headers={'x-request-id':'fixture-busy-request'})
        error=APIStatusError('Service is too busy',response=response,body={'error':{'code':'service_unavailable_error'}})
        message=model_error_message(error)
        self.assertIn('模型服务暂时繁忙',message)
        self.assertIn('503',message)
        self.assertIn('稍后',message)
        self.assertIn('fixture-busy-request',message)

    async def test_busy_request_identifier_can_come_from_provider_message(self):
        from app.management.runtime import model_error_message
        response=httpx.Response(503,request=httpx.Request('POST','https://fixture.invalid'))
        error=APIStatusError('Service is too busy',response=response,body={'error':{'message':'Service is too busy. (request_id: fixture-from-body)'}})
        self.assertIn('fixture-from-body',model_error_message(error))

    async def test_model_error_remains_readable_inside_mcp_task_group(self):
        from app.management.runtime import model_error_message
        response=httpx.Response(503,request=httpx.Request('POST','https://fixture.invalid'))
        error=APIStatusError('Service is too busy',response=response,body={})
        wrapped=ExceptionGroup('unhandled errors in a TaskGroup',[ExceptionGroup('nested MCP context',[error])])
        self.assertIn('模型服务暂时繁忙',model_error_message(wrapped))

    async def test_failed_task_reports_busy_service_and_retains_uploaded_document(self):
        from app.agent.main_agent import run_deep_agent
        from app.api.monitor import test_trace
        response=httpx.Response(503,request=httpx.Request('POST','https://fixture.invalid'),headers={'x-request-id':'fixture-task-request'})
        error=APIStatusError('Service is too busy',response=response,body={})
        events=[];token=test_trace.set(events)
        try:
            with tempfile.TemporaryDirectory() as folder:
                root=Path(folder)
                attachments=root/'updated/session_fixture-busy-task'
                attachments.mkdir(parents=True)
                (attachments/'fixture.txt').write_text('synthetic fixture',encoding='utf-8')
                with patch('app.agent.main_agent.project_root_path',root),patch('app.agent.main_agent.build_main_agent',side_effect=error):
                    await run_deep_agent('fixture question','fixture-busy-task',snapshot={'agents':[],'resources':{}})
                self.assertTrue((attachments/'fixture.txt').is_file())
            message=next(event['message'] for event in events if event['event']=='error')
            self.assertIn('模型服务暂时繁忙',message)
            self.assertIn('fixture-task-request',message)
            self.assertEqual(events[-1]['event'],'document_index_released')
            self.assertFalse(any(event['event']=='task_result' for event in events))
        finally:
            test_trace.reset(token)


if __name__=='__main__':unittest.main()
