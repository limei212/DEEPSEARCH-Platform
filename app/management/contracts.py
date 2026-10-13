import json
import re

from jsonschema import Draft202012Validator

from .models import BUILTIN_TOOLS
from .connectors import mcp_tool_name


def input_schema(config):
    if config.get('input_schema') is not None:
        return config['input_schema']
    properties = {}
    required = []
    for field in config['input_fields']:
        spec = {'type':field['type'], 'description':field.get('description','')}
        if field.get('enum'):
            spec['enum'] = field['enum']
        properties[field['name']] = spec
        if field['required']:
            required.append(field['name'])
    return {'type':'object','properties':properties,'required':required}


def validate_config(config):
    if not config['system_prompt'].strip():
        raise ValueError('请填写系统提示词')
    if set(config['builtin_tools']) - set(BUILTIN_TOOLS):
        raise ValueError('存在未知内置工具')
    for schema in [input_schema(config), config['output_schema'] if config['output_format'] == 'json' else None]:
        if schema is not None:
            Draft202012Validator.check_schema(schema)
            def check_refs(value):
                if isinstance(value, dict):
                    if '$ref' in value and not str(value['$ref']).startswith('#'):
                        raise ValueError('Schema 只支持本地 $ref，不支持外部 URL 引用')
                    for item in value.values():
                        check_refs(item)
                elif isinstance(value, list):
                    for item in value:
                        check_refs(item)
            check_refs(schema)
            if schema.get('type') != 'object':
                raise ValueError('输入输出 Schema 的根类型必须是 object')
    names = {field['name'] for field in config['input_fields']} | set(input_schema(config).get('properties', {})) | {'query','files','context','output_format'}
    unknown = set(re.findall(r'\{\{\s*(\w+)\s*\}\}',config['system_prompt'])) - names
    if unknown:
        raise ValueError('提示词中存在未定义变量：' + '、'.join(sorted(unknown)))
    if config['artifacts'] and 'generate_markdown' not in config['builtin_tools']:
        raise ValueError('生成交付文件需要连接「生成 Markdown」工具')
    if 'pdf' in config['artifacts'] and 'convert_md_to_pdf' not in config['builtin_tools']:
        raise ValueError('生成 PDF 需要连接「转换 PDF」工具')


def resolve_input(config, values, *, files=None, context=''):
    if isinstance(values, str):
        try:
            candidate = json.loads(values)
            values = candidate if isinstance(candidate,dict) else {'query':values}
        except ValueError:
            values = {'query':values}
    result = dict(values)
    for field in config['input_fields']:
        name = field['name']
        if field['source'] == 'files' and files is not None:
            result[name] = files
            continue
        if field['source'] == 'context' and context:
            result[name] = context
            continue
        if name in result:
            continue
        if field['source'] == 'query' and 'query' in values:
            result[name] = values['query']
        elif field['source'] == 'files':
            result[name] = files or []
        elif field['source'] == 'context':
            result[name] = context
        elif field.get('default') is not None:
            result[name] = field['default']
    schema = input_schema(config)
    if schema.get('additionalProperties') is False:
        result = {key:value for key,value in result.items() if key in schema.get('properties',{})}
    errors = sorted(Draft202012Validator(schema).iter_errors(result),key=lambda error:str(error.path))
    if errors:
        raise ValueError('输入校验失败：' + errors[0].message)
    return result


def render_prompt(config, values, resources):
    variables = dict(values, output_format=config['output_format'])
    prompt = re.sub(r'\{\{\s*(\w+)\s*\}\}',lambda match: str(variables.get(match[1],'')) if isinstance(variables.get(match[1],''),str) else json.dumps(variables.get(match[1],''),ensure_ascii=False),config['system_prompt'])
    parts = [prompt, '【输入约定】\n' + json.dumps(input_schema(config),ensure_ascii=False),
        '【输出要求】\n输出格式：'+config['output_format']]
    if config['output_format'] == 'json':
        parts.append('输出必须符合 JSON Schema：'+json.dumps(config['output_schema'],ensure_ascii=False))
    if config['required_sections']:
        parts.append('结果必须包含这些标题或字段：'+'、'.join(config['required_sections']))
    if config['artifacts']:
        parts.append('需要生成交付文件：'+'、'.join(config['artifacts']))
    if config['builtin_tools']:
        parts.append('【内置工具】\n'+'、'.join(config['builtin_tools']))
    for binding in config['knowledge']:
        resource = resources.get(binding['resource_id'])
        if resource:
            selected = [chat for chat in resource.get('discovery',{}).get('chats',[]) if chat['id'] in binding['chat_ids']]
            parts.append('【知识库连接】\n'+resource['name']+'：'+json.dumps(selected,ensure_ascii=False))
    for identifier in config['skill_ids']:
        resource = resources.get(identifier)
        if resource:
            parts.append('【可用 Skill】\n'+resource['name']+'：'+resource['description']+'。通过 read_skill 获取完整指令和附属文件。')
    for binding in config['mcp']:
        resource = resources.get(binding['resource_id'])
        if resource:
            selected = [dict(tool, call_name=mcp_tool_name(resource['id'], tool['name'])) for tool in resource.get('discovery',{}).get('tools',[]) if tool['name'] in binding['tools']]
            parts.append('【MCP 工具】\n'+resource['name']+'：'+json.dumps(selected,ensure_ascii=False))
    parts.append('【系统工作规则】\n仅在本任务工作目录中处理文件。资料不足时说明缺口，不编造数据、来源或工具结果。')
    return '\n\n'.join(parts)


def validate_output(config, result):
    if config['output_format'] == 'json':
        if isinstance(result,str):
            try:
                result = json.loads(result.strip().removeprefix('```json').removesuffix('```').strip())
            except ValueError as error:
                raise ValueError('输出校验失败：返回内容不是有效 JSON') from error
        Draft202012Validator(config['output_schema']).validate(result)
        missing = [section for section in config['required_sections'] if section not in result]
    else:
        missing = [section for section in config['required_sections'] if section not in str(result)]
    if missing:
        raise ValueError('输出校验失败，缺少：'+'、'.join(missing))
    return result
