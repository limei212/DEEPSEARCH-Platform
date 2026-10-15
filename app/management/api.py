import asyncio
import json
import os
import uuid
import zipfile
from pathlib import Path

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
from jsonschema.exceptions import SchemaError, ValidationError

from app.api.context import set_session_context, set_thread_context, reset_session_context
from app.api.monitor import test_trace
from .models import AgentConfig, ResourceConfig, BUILTIN_TOOLS
from .store import ConflictError, get_store
from .connectors import import_skill, probe_resource, redact_error
from .contracts import render_prompt, resolve_input, validate_config
from .runtime import runtime_status, run_single, model_error_message

load_dotenv(Path(__file__).resolve().parents[2] / '.env')


def frontend_origins():
    return [origin.strip().rstrip('/') for origin in os.getenv(
        'FRONTEND_ORIGINS', 'http://127.0.0.1:5173,http://localhost:5173'
    ).split(',') if origin.strip()]


def check_management_origin(request: Request):
    origin = request.headers.get('origin')
    if origin is not None and origin not in frontend_origins():
        raise HTTPException(status_code=403, detail='不允许此网页访问助手管理接口')


router = APIRouter(prefix='/api/manage', tags=['Agent 管理'], dependencies=[Depends(check_management_origin)])


def error_response(error):
    return HTTPException(status_code=409 if isinstance(error,ConflictError) else 400,detail=str(error))


@router.get('/catalog')
def catalog():
    store = get_store()
    resources = store.list_resources()
    by_id = {item['id']:item for item in resources}
    agents = store.list_agents()
    for agent in agents:
        agent['status'] = runtime_status(agent,by_id)
    return {'agents':agents,'resources':resources,'builtin_tools':[{'id':identifier,'name':name} for identifier,name in BUILTIN_TOOLS.items()]}


@router.post('/agents')
def save_agent(config: AgentConfig, publish: bool = False):
    try:
        return get_store().save_agent(config,publish=publish)
    except (ValueError,SchemaError) as error:
        raise error_response(error) from error


@router.post('/agents/{identifier}/disable')
def disable_agent(identifier: str):
    try:
        return get_store().disable_agent(identifier)
    except ValueError as error:
        raise error_response(error) from error


@router.get('/agents/{identifier}/versions')
def versions(identifier: str):
    return get_store().versions(identifier)


@router.post('/agents/{identifier}/restore/{version}')
def restore_agent(identifier: str,version: int):
    try:
        return get_store().restore_agent(identifier,version)
    except ValueError as error:
        raise error_response(error) from error


class PreviewRequest(BaseModel):
    agent: AgentConfig
    values: dict = Field(default_factory=lambda:{'query':'请研究品类策略'})


def draft_resources(agent):
    ids = {item.resource_id for item in agent.knowledge+agent.mcp} | set(agent.skill_ids)
    return {identifier:get_store().get_resource(identifier,private=True) for identifier in ids}


def public_test_result(value, resources):
    serialized = json.dumps(value, ensure_ascii=False)
    for resource in resources.values():
        if resource.get('secret'):
            serialized = serialized.replace(json.dumps(resource['secret'], ensure_ascii=False)[1:-1], '[密钥已隐藏]')
    return json.loads(serialized)


@router.post('/preview')
def preview(request: PreviewRequest):
    try:
        config = request.agent.model_dump()
        validate_config(config)
        values = resolve_input(config,request.values)
        return {'prompt':render_prompt(config,values,draft_resources(request.agent)),'input':values}
    except (ValueError,SchemaError,ValidationError) as error:
        raise error_response(error) from error


class TestRequest(PreviewRequest):
    thread_id: str = Field(default_factory=lambda:str(uuid.uuid4()),pattern=r'^[a-zA-Z0-9_-]{1,100}$')


@router.post('/test')
async def test_agent(request: TestRequest):
    config = request.agent.model_dump()
    resources = {}
    try:
        validate_config(config)
        resources = draft_resources(request.agent)
        get_store().validate_agent(config)
    except (ValueError,SchemaError) as error:
        raise error_response(error) from error
    directory = Path(__file__).resolve().parents[1] / 'output' / ('session_'+request.thread_id)
    directory.mkdir(parents=True,exist_ok=True)
    upload_dir = Path(__file__).resolve().parents[1] / 'updated' / ('session_'+request.thread_id)
    if upload_dir.exists():
        import shutil
        for file in upload_dir.iterdir():
            if file.is_file():
                shutil.copy2(file,directory/file.name)
    trace = []
    trace_token = test_trace.set(trace)
    session_token = set_session_context(str(directory))
    thread_token = set_thread_context(request.thread_id)
    try:
        async with asyncio.timeout(180):
            result = await run_single(config,resources,request.values,directory)
        files = [{'name':file.name,'path':str(file)} for file in directory.iterdir() if file.is_file()]
        return public_test_result({'status':'success','result':result,'events':trace,'files':files,'input':request.values,'revision':config['revision']}, resources)
    except Exception as error:
        message = model_error_message(error)
        for resource in resources.values():
            if resource.get('secret'):
                message = message.replace(resource['secret'],'[密钥已隐藏]')
        return public_test_result({'status':'error','message':message[:1500],'events':trace,'files':[]}, resources)
    finally:
        test_trace.reset(trace_token)
        reset_session_context(session_token,thread_token)


@router.post('/resources')
def save_resource(config: ResourceConfig):
    try:
        return get_store().save_resource(config)
    except (ValueError,SchemaError) as error:
        raise error_response(error) from error


@router.post('/resources/{identifier}/probe')
async def probe(identifier: str):
    try:
        resource = get_store().get_resource(identifier,private=True)
        result = await probe_resource(resource)
        return get_store().record_probe(identifier,result,revision=resource['revision'])
    except ValueError as error:
        raise error_response(error) from error


@router.post('/skills/import')
async def upload_skill(file: UploadFile = File(...)):
    try:
        data = await file.read(5*1024*1024+1)
        resource = import_skill(data,file.filename or '')
        return get_store().save_resource(ResourceConfig(**resource))
    except (ValueError,UnicodeError,zipfile.BadZipFile) as error:
        raise error_response(error) from error
