import asyncio
import json
import socket
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from app.management.connectors import probe_resource
from app.management.models import AgentConfig
from app.management.runtime import connected_tools


class ConnectorTests(unittest.IsolatedAsyncioTestCase):
    async def test_http_mcp_discovery(self):
        with socket.socket() as port_socket:
            port_socket.bind(('127.0.0.1',0));port=port_socket.getsockname()[1]
        process=subprocess.Popen([sys.executable,str(Path(__file__).parent/'fixtures/mcp_echo.py'),'--http',str(port)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            async with httpx.AsyncClient() as client:
                for _ in range(80):
                    if process.poll() is not None:
                        self.fail('测试 MCP 服务提前退出')
                    try:
                        await client.get(f'http://127.0.0.1:{port}/mcp',timeout=.5)
                        break
                    except httpx.HTTPError:
                        await asyncio.sleep(.15)
            result=await probe_resource({'id':'test','kind':'mcp','name':'HTTP fixture','config':{'transport':'http','url':f'http://127.0.0.1:{port}/mcp'},'secret':''})
            self.assertEqual(result['status'],'ready',result)
            self.assertIn('echo',{item['name'] for item in result['tools']})
        finally:
            process.terminate();process.wait(timeout=10)

    async def test_ragflow_discovery_query_and_cleanup_keep_citations(self):
        calls=[]
        async def handle(request):
            calls.append((request.method,request.url.path))
            self.assertEqual(request.headers['authorization'],'Bearer fixture-key')
            path=request.url.path
            if path.endswith('/chats'):
                data=[{'id':'chat','name':'白皮书助手','dataset_ids':['dataset']}]
            elif path.endswith('/datasets'):
                data=[{'id':'dataset','name':'公司白皮书'}]
            elif path.endswith('/sessions') and request.method=='POST':
                data={'id':'temporary-session'}
            elif path.endswith('/completions'):
                data={'answer':'品类应聚焦核心客群','reference':{'chunks':[{'document_name':'白皮书.pdf','content':'来源依据'}]}}
            else:
                data=True
            return httpx.Response(200,json={'code':0,'data':data})
        original_client=httpx.AsyncClient
        resource={'id':'kb-fixture','kind':'knowledge','name':'内部连接','config':{'url':'http://ragflow.test'},'secret':'fixture-key'}
        with patch('app.management.connectors.httpx.AsyncClient',side_effect=lambda **kwargs: original_client(transport=httpx.MockTransport(handle),**kwargs)):
            probe=await probe_resource(resource)
            self.assertEqual(probe['chats'][0]['datasets'],['公司白皮书'])
            resource['discovery']=probe
            config=AgentConfig(name='助手',description='知识查询',knowledge=[{'resource_id':'kb-fixture','chat_ids':['chat']}]).model_dump()
            async with connected_tools(config,{'kb-fixture':resource}) as tools:
                choices=json.loads(await tools[0].ainvoke({}))
                result=await tools[1].ainvoke({'chat_name':choices[0]['name'],'question':'品类策略'})
                self.assertIn('白皮书.pdf',result)
        self.assertIn(('DELETE','/api/v1/chats/chat/sessions'),calls)


if __name__=='__main__':
    unittest.main()
