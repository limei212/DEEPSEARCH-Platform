import asyncio
import io
import hashlib
import json
import re
import zipfile
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import PurePosixPath
from urllib.parse import urlparse

import httpx
import yaml


def mcp_tool_name(resource_id, name):
    return 'mcp_' + resource_id.replace('-', '')[:8] + '_' + re.sub(r'[^a-zA-Z0-9_-]', '_', name)[:32] + '_' + hashlib.sha256(name.encode()).hexdigest()[:6]


def validate_resource(resource):
    config = resource['config']
    if resource['kind'] == 'skill':
        content = config.get('content','')
        if not content.strip():
            raise ValueError('请填写或导入 SKILL.md 内容')
        parse_skill(content)
        if len(json.dumps(config,ensure_ascii=False).encode()) > 5*1024*1024:
            raise ValueError('技能包不得超过 5MB')
        for path in config.get('files',{}):
            safe_skill_path(path)
    else:
        if resource['kind'] == 'mcp' and config.get('transport') == 'stdio':
            if not config.get('command','').strip() or not isinstance(config.get('args',[]),list):
                raise ValueError('本地 MCP 需要启动命令和参数列表')
        else:
            url = urlparse(config.get('url',''))
            if url.scheme not in ('http','https') or not url.netloc or url.username or url.password:
                raise ValueError('请填写有效的 HTTP/HTTPS 服务地址，认证信息填写在密钥栏')
        if resource['kind'] == 'mcp' and config.get('transport','http') not in ('http','sse','stdio'):
            raise ValueError('不支持的 MCP 连接方式')


def parse_skill(content):
    match = re.match(r'^---\s*\n(.*?)\n---\s*(?:\n|$)',content,re.S)
    if not match:
        raise ValueError('SKILL.md 需要 YAML 头部，包含 name 和 description')
    try:
        metadata = yaml.safe_load(match[1])
    except yaml.YAMLError as error:
        raise ValueError('Skill YAML 头部格式错误，请检查缩进和字段格式') from error
    if not isinstance(metadata,dict) or not isinstance(metadata.get('name'),str) or not isinstance(metadata.get('description'),str) or not metadata['name'].strip() or not metadata['description'].strip():
        raise ValueError('Skill 的 name 和 description 不能为空')
    return metadata


def safe_skill_path(path):
    value = PurePosixPath(path.replace('\\','/'))
    if value.is_absolute() or '..' in value.parts or ':' in path or not value.parts:
        raise ValueError('技能包包含非法文件路径')
    return str(value)


def import_skill(data, filename):
    if len(data) > 5*1024*1024:
        raise ValueError('技能包不得超过 5MB')
    if filename.lower().endswith('.zip'):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = [entry for entry in archive.infolist() if not entry.is_dir()]
            if sum(entry.file_size for entry in entries) > 5*1024*1024 or len(entries) > 100:
                raise ValueError('技能包展开后不得超过 5MB 或 100 个文件')
            names = [safe_skill_path(entry.filename) for entry in entries]
            roots = [name for name in names if name.split('/')[-1] == 'SKILL.md']
            if len(roots) != 1:
                raise ValueError('每次导入应包含一个 SKILL.md')
            prefix = roots[0][:-len('SKILL.md')]
            files = {}
            for entry,name in zip(entries,names):
                if not name.startswith(prefix) or ((entry.external_attr >> 16) & 0o170000) == 0o120000:
                    raise ValueError('技能包包含根目录之外的文件或符号链接')
                try:
                    files[name[len(prefix):]] = archive.read(entry).decode('utf-8-sig')
                except UnicodeError as error:
                    raise ValueError('首版技能包仅支持 UTF-8 文本文件') from error
            content = files.pop('SKILL.md')
    elif filename.lower().endswith('.md'):
        content = data.decode('utf-8-sig'); files = {}
    else:
        raise ValueError('请选择 SKILL.md 或 ZIP 技能包')
    metadata = parse_skill(content)
    dependencies = metadata.get('required_tools',[])
    if not isinstance(dependencies,list) or not all(isinstance(item,str) for item in dependencies):
        raise ValueError('required_tools 必须为工具名称列表')
    return {'kind':'skill','name':metadata['name'],'description':metadata['description'],
        'config':{'content':content,'files':files,'version':str(metadata.get('version','1.0')),'required_tools':dependencies}}


@asynccontextmanager
async def mcp_session(resource):
    from contextlib import AsyncExitStack
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from mcp.client.streamable_http import streamable_http_client
    from mcp.client.sse import sse_client
    config = resource['config']
    headers = {'Authorization':'Bearer '+resource['secret']} if resource.get('secret') else None
    async with AsyncExitStack() as stack:
        if config.get('transport','http') == 'stdio':
            params = StdioServerParameters(command=config['command'],args=config.get('args',[]))
            read,write = await stack.enter_async_context(stdio_client(params))
        elif config.get('transport') == 'sse':
            read,write = await stack.enter_async_context(sse_client(config['url'],headers=headers,timeout=15,sse_read_timeout=60))
        else:
            client = await stack.enter_async_context(httpx.AsyncClient(headers=headers,timeout=30))
            read,write,_ = await stack.enter_async_context(streamable_http_client(config['url'],http_client=client))
        session = await stack.enter_async_context(ClientSession(read,write,read_timeout_seconds=timedelta(seconds=30)))
        await session.initialize()
        yield session


def redact_error(error, resource):
    def reason(value):
        children = getattr(value, 'exceptions', None)
        return '; '.join(reason(child) for child in children[:3]) if children else (str(value) or type(value).__name__)
    message = reason(error)
    secret = resource.get('secret','')
    if secret:
        message = message.replace(secret,'[密钥已隐藏]')
    return message[:800] or type(error).__name__


async def rag_request(resource, path, *, method='GET', body=None):
    if not resource.get('secret') or 'your' in resource['secret'].lower() or resource['secret'].startswith('你的'):
        raise ValueError('请先配置 RAGFlow API Key')
    base = resource['config']['url'].rstrip('/')
    if not base.endswith('/api/v1'):
        base += '/api/v1'
    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.request(method,base+path,headers={'Authorization':'Bearer '+resource['secret']},json=body)
        response.raise_for_status()
        payload = response.json()
        if payload.get('code') not in (0,None):
            raise ValueError(str(payload.get('message','RAGFlow 返回错误')))
        return payload.get('data',payload)


async def probe_resource(resource):
    try:
        if resource['kind'] == 'skill':
            validate_resource(resource)
            return {'status':'ready','message':'技能内容有效','files':list(resource['config'].get('files',{}))}
        if resource['kind'] == 'knowledge':
            chats = await rag_request(resource,'/chats?page_size=1000')
            datasets = await rag_request(resource,'/datasets?page_size=1000')
            names = {item['id']:item['name'] for item in datasets}
            normalized = [{'id':item['id'],'name':item['name'],'dataset_ids':item.get('dataset_ids',[]),
                'datasets':[names.get(identifier,identifier) for identifier in item.get('dataset_ids',[])]} for item in chats]
            return {'status':'ready','message':f'发现 {len(normalized)} 个聊天助手、{len(datasets)} 个知识库', 'chats':normalized,
                'datasets':[{'id':item['id'],'name':item['name']} for item in datasets]}
        async with asyncio.timeout(35):
            async with mcp_session(resource) as session:
                result = await session.list_tools()
                tools = [{'name':item.name,'description':item.description or '', 'inputSchema':item.inputSchema} for item in result.tools]
                return {'status':'ready','message':f'发现 {len(tools)} 个工具','tools':tools}
    except Exception as error:
        return {'status':'error','message':redact_error(error,resource)}
