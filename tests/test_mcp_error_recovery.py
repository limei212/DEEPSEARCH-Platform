import sys
import unittest
from pathlib import Path

from app.api.monitor import test_trace
from app.management.models import AgentConfig
from app.management.runtime import ToolTrace,connected_tools

class MCPErrorRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_page_failure_returns_error_message_and_connection_can_continue(self):
        resource={'id':'fixture','kind':'mcp','name':'Page fixture','config':{'transport':'stdio','command':sys.executable,'args':[str(Path(__file__).parent/'fixtures/mcp_page_error.py')]}}
        agent=AgentConfig(name='网页助手',description='test',mcp=[{'resource_id':'fixture','tools':['page']}]).model_dump()
        events=[];token=test_trace.set(events)
        try:
            async with connected_tools(agent,{'fixture':resource}) as tools:
                call=tools[0]
                bad=await call.ainvoke({'type':'tool_call','id':'bad-page','name':call.name,'args':{'url':'https://fixture.invalid/missing'}},config={'callbacks':[ToolTrace()]})
                self.assertEqual(bad.status,'error')
                self.assertIn('页面访问超时',bad.content)
                good=await call.ainvoke({'type':'tool_call','id':'good-page','name':call.name,'args':{'url':'https://fixture.invalid/available'}},config={'callbacks':[ToolTrace()]})
                self.assertEqual(good.status,'success')
                self.assertIn('已读取虚拟网页',good.content)
            failed=[event for event in events if event['event']=='tool_error']
            self.assertEqual(len(failed),1)
            self.assertIn('页面访问超时',failed[0]['data']['reason'])
            self.assertTrue(any(event['event']=='tool_result' for event in events))
        finally:test_trace.reset(token)

if __name__=='__main__':unittest.main()
