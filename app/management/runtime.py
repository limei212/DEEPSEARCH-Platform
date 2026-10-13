import json
import os
import re
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

from deepagents import create_deep_agent, GeneralPurposeSubagentProfile, HarnessProfile, register_harness_profile
from deepagents.backends import FilesystemBackend
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from langchain_core.tools import StructuredTool
from langchain_core.callbacks import AsyncCallbackHandler
from langgraph.checkpoint.memory import InMemorySaver

from app.api.monitor import monitor
from .connectors import mcp_session, rag_request, safe_skill_path, mcp_tool_name
from .contracts import input_schema, render_prompt, resolve_input, validate_output

checkpointer = InMemorySaver()
register_harness_profile('openai', HarnessProfile(general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False), excluded_tools=frozenset({'execute'})))


class ToolTrace(AsyncCallbackHandler):
    async def on_tool_end(self, output, *, run_id, **kwargs):
        value = output.content if hasattr(output, 'content') else str(output)
        monitor._emit('tool_result', '工具已返回结果', {'result': str(value)[:12000]})

    async def on_tool_error(self, error, *, run_id, **kwargs):
        monitor._emit('tool_error', '工具执行失败', {'reason': str(error)[:1500]})


def key_configured(value):
    return bool(value and not any(marker in value.lower() for marker in ['placeholder','your_','your-','replace','你的','changeme']))


def runtime_status(agent, resources):
    if not agent.get('version'):
        return 'draft'
    if not agent.get('enabled',True):
        return 'disabled'
    if not key_configured(os.getenv('OPENAI_API_KEY')):
        return 'unconfigured'
    if 'internet_search' in agent['builtin_tools'] and not key_configured(os.getenv('TAVILY_API_KEY')):
        return 'unconfigured'
    if any(name in agent['builtin_tools'] for name in ['execute_sql_query','list_sql_tables','get_table_data']) and not os.getenv('MYSQL_HOST'):
        return 'unconfigured'
    ids = [binding['resource_id'] for binding in agent['knowledge']+agent['mcp']] + agent['skill_ids']
    if any(resources.get(identifier,{}).get('status') != 'ready' for identifier in ids):
        return 'unconfigured'
    for binding in agent['knowledge']:
        available = {chat['id'] for chat in resources[binding['resource_id']].get('discovery', {}).get('chats', [])}
        if not binding['chat_ids'] or not set(binding['chat_ids']) <= available:
            return 'unconfigured'
    for binding in agent['mcp']:
        available = {tool['name'] for tool in resources[binding['resource_id']].get('discovery', {}).get('tools', [])}
        if not binding['tools'] or not set(binding['tools']) <= available:
            return 'unconfigured'
    return 'enabled'


def model_for(agent):
    if not key_configured(os.getenv('OPENAI_API_KEY')):
        raise ValueError('尚未配置可用的模型 API Key，请填写项目 .env 后重启后端')
    name = agent.get('model_name') or os.getenv('LLM_QWEN_MAX')
    if not name:
        raise ValueError('尚未配置模型名称 LLM_QWEN_MAX')
    return init_chat_model(model=name,model_provider='openai',timeout=60,max_retries=1)


def builtin_tools():
    from app.tools.tavily_tool import internet_search
    from app.tools.db_tools import list_sql_tables, get_table_data, execute_sql_query
    from app.tools.upload_file_read_tool import read_file_content
    from app.tools.markdown_tools import generate_markdown
    from app.tools.pdf_tools import convert_md_to_pdf
    return {item.name:item for item in [internet_search,list_sql_tables,get_table_data,execute_sql_query,read_file_content,generate_markdown,convert_md_to_pdf]}


@asynccontextmanager
async def connected_tools(agent, resources):
    tools = [builtin_tools()[name] for name in agent['builtin_tools']]
    async with AsyncExitStack() as stack:
        if agent['knowledge']:
            selections = {}
            for binding in agent['knowledge']:
                resource = resources[binding['resource_id']]
                for chat in resource.get('discovery',{}).get('chats',[]):
                    if chat['id'] in binding['chat_ids']:
                        qualified_name = resource['name'] + ' / ' + chat['name'] + ' [' + resource['id'][:8] + ']'
                        selections[qualified_name] = (resource, dict(chat, name=qualified_name))

            def get_assistant_list():
                monitor.report_tool('get_assistant_list')
                return json.dumps([chat for _,chat in selections.values()],ensure_ascii=False)

            async def create_ask_delete(chat_name: str, question: str):
                if chat_name not in selections:
                    raise ValueError('只能查询当前助手已连接的 RAGFlow 聊天助手')
                resource,chat = selections[chat_name]
                monitor.report_tool('create_ask_delete',{'chat_name':chat_name,'question':question})
                session = await rag_request(resource,f"/chats/{chat['id']}/sessions",method='POST',body={'name':'DeepSearch 临时查询'})
                try:
                    result = await rag_request(resource,f"/chats/{chat['id']}/completions",method='POST',body={'question':question,'stream':False,'session_id':session['id']})
                    monitor._emit('tool_result','知识库已返回结果',{'tool_name':'create_ask_delete','result':result})
                    return json.dumps(result,ensure_ascii=False)
                finally:
                    await rag_request(resource,f"/chats/{chat['id']}/sessions",method='DELETE',body={'ids':[session['id']]})

            tools.extend([StructuredTool.from_function(get_assistant_list,description='列出当前已连接的 RAGFlow 聊天助手及其知识库'),
                StructuredTool.from_function(coroutine=create_ask_delete,name='create_ask_delete',description='向已连接的 RAGFlow 聊天助手提问，返回原始答案及服务提供的来源信息')])
        if agent['skill_ids']:
            skills = {identifier:resources[identifier] for identifier in agent['skill_ids']}

            def read_skill(skill_id: str, file: str = 'SKILL.md'):
                resource = skills.get(skill_id) or next((item for item in skills.values() if item['name'] == skill_id),None)
                if not resource:
                    raise ValueError('只能读取已连接的 Skill')
                path = safe_skill_path(file)
                result = resource['config']['content'] if path == 'SKILL.md' else resource['config'].get('files',{}).get(path)
                if result is None:
                    raise ValueError('Skill 文件不存在')
                monitor._emit('skill_loaded','已加载技能：'+resource['name'],{'skill':resource['name'],'file':path})
                return result

            tools.append(StructuredTool.from_function(read_skill,description='读取已连接 Skill 的 SKILL.md 或附属 UTF-8 文本文件；skill_id 可以为名称或 ID。技能脚本在这里作为文本读取，不自动执行。'))
        for binding in agent['mcp']:
            resource = resources[binding['resource_id']]
            session = await stack.enter_async_context(mcp_session(resource))
            discovered = (await session.list_tools()).tools
            for spec in discovered:
                if spec.name not in binding['tools']:
                    continue
                def wrapper(session=session, spec=spec, resource=resource):
                    async def call(**arguments):
                        monitor.report_tool(spec.name,arguments)
                        result = await session.call_tool(spec.name,arguments)
                        if result.isError:
                            raise ValueError('MCP 工具返回错误：'+str(result.content))
                        serialized = result.model_dump(mode='json')
                        monitor._emit('tool_result','MCP 工具已返回结果',{'tool_name':spec.name,'result':serialized})
                        return json.dumps(serialized,ensure_ascii=False)
                    name = mcp_tool_name(resource['id'], spec.name)
                    return StructuredTool.from_function(coroutine=call,name=name,description=spec.description or spec.name,args_schema=spec.inputSchema)
                tools.append(wrapper())
            if not set(binding['tools']) <= {item.name for item in discovered}:
                raise ValueError('MCP 工具清单已变化，请刷新资源连接并重新选择工具')
        yield tools


async def run_single(agent, resources, values, directory: Path, *, runnable_config=None, context=''):
    inputs = resolve_input(agent,values,files=[file.name for file in directory.iterdir() if file.is_file()], context=context)
    previous_files = {file.name:file.stat().st_mtime_ns for file in directory.iterdir() if file.is_file()}
    prompt = render_prompt(agent,inputs,resources)
    monitor._emit('agent_config','使用助手配置',{'name':agent['name'],'version':agent.get('version',0),'input':inputs})
    model = model_for(agent)
    runnable_config = dict(runnable_config or {})
    runnable_config['callbacks'] = [*(runnable_config.get('callbacks') or []), ToolTrace()] if isinstance(runnable_config.get('callbacks'), list) else [ToolTrace()]
    async with connected_tools(agent,resources) as tools:
        graph = create_deep_agent(model=model,system_prompt=prompt,tools=tools,backend=FilesystemBackend(root_dir=directory,virtual_mode=True),
            response_format=agent['output_schema'] if agent['output_format'] == 'json' else None)
        result = await graph.ainvoke({'messages':[{'role':'user','content':json.dumps(inputs,ensure_ascii=False)}]},config=runnable_config)
    answer = result.get('structured_response') if agent['output_format'] == 'json' else result['messages'][-1].text
    validated = validate_output(agent,answer)
    for artifact in agent['artifacts']:
        extension = '.pdf' if artifact == 'pdf' else '.md'
        if not any(previous_files.get(file.name) != file.stat().st_mtime_ns for file in directory.glob('*'+extension)):
            raise ValueError('交付校验失败：未生成 '+artifact+' 文件')
    monitor._emit('output_validated','助手输出校验通过',{'name':agent['name'],'format':agent['output_format']})
    return validated


def build_main_agent(snapshot, directory, task_context=''):
    from app.agent.prompts import main_agent_content
    subagents = []
    available_agents = [agent for agent in snapshot['agents'] if runtime_status(agent, snapshot['resources']) == 'enabled']
    for agent in available_agents:
        def runnable(agent=agent):
            async def invoke(state, config=None):
                message = state['messages'][-1]
                text = message.text if hasattr(message,'text') else message.get('content','')
                result = await run_single(agent,snapshot['resources'],text,directory,runnable_config=config,context=task_context)
                content = result if isinstance(result,str) else json.dumps(result,ensure_ascii=False)
                return {'messages':[AIMessage(content=content)]}
            return RunnableLambda(invoke)
        subagents.append({'name':agent['id'],'description':agent['name']+'：'+agent['description']+'\n输入必须符合：'+json.dumps(input_schema(agent),ensure_ascii=False),'runnable':runnable()})
    instruction = '\n\n当前可用助手只来自下列配置，禁止调用未列出的助手。调用 task 时 subagent_type 使用对应 ID，description 中用 JSON 提供助手要求的输入字段。未配置或未启用的助手不可调度；没有合适助手时说明缺少的能力。\n'+json.dumps([{'id':agent['id'],'name':agent['name'],'description':agent['description']} for agent in available_agents],ensure_ascii=False)
    library = builtin_tools()
    return create_deep_agent(model=model_for({}),system_prompt=main_agent_content['system_prompt']+instruction,
        tools=[library[name] for name in ['generate_markdown','convert_md_to_pdf','read_file_content']],checkpointer=checkpointer,
        backend=FilesystemBackend(root_dir=directory,virtual_mode=True),subagents=subagents)
