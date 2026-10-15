from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class InputField(BaseModel):
    name: str = Field(pattern=r'^[A-Za-z_][A-Za-z0-9_]*$')
    type: Literal['string', 'number', 'boolean', 'array', 'object'] = 'string'
    required: bool = False
    description: str = ''
    source: Literal['query', 'files', 'context', 'manual'] = 'manual'
    default: Any = None
    enum: list[str] = Field(default_factory=list)


class KnowledgeBinding(BaseModel):
    resource_id: str
    chat_ids: list[str] = Field(default_factory=list)


class MCPBinding(BaseModel):
    resource_id: str
    tools: list[str] = Field(default_factory=list)


class AgentConfig(BaseModel):
    id: str | None = None
    revision: int = 0
    name: str = Field(min_length=1, max_length=60)
    description: str = Field(min_length=1, max_length=3000)
    icon: Literal['research', 'database', 'knowledge', 'spark'] = 'spark'
    system_prompt: str = Field(default='', max_length=60000)
    model_name: str = Field(default='', max_length=200)
    builtin_tools: list[str] = Field(default_factory=list)
    input_fields: list[InputField] = Field(default_factory=lambda: [InputField(name='query', required=True, source='query', description='本次任务问题')])
    input_schema: dict[str, Any] | None = None
    output_format: Literal['text', 'markdown', 'json'] = 'markdown'
    output_schema: dict[str, Any] = Field(default_factory=lambda: {'type':'object','properties':{'answer':{'type':'string'}},'required':['answer']})
    required_sections: list[str] = Field(default_factory=list)
    artifacts: list[Literal['markdown', 'pdf']] = Field(default_factory=list)
    knowledge: list[KnowledgeBinding] = Field(default_factory=list)
    skill_ids: list[str] = Field(default_factory=list)
    mcp: list[MCPBinding] = Field(default_factory=list)

    @field_validator('name', 'description')
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError('内容不能为空')
        return value.strip()

    @field_validator('input_fields')
    @classmethod
    def unique_fields(cls, value):
        if len({field.name for field in value}) != len(value):
            raise ValueError('输入字段名称不能重复')
        return value


class ResourceConfig(BaseModel):
    id: str | None = None
    revision: int = 0
    kind: Literal['knowledge', 'skill', 'mcp']
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default='', max_length=3000)
    config: dict[str, Any] = Field(default_factory=dict)
    secret: str | None = Field(default=None, max_length=10000)
    clear_secret: bool = False


BUILTIN_TOOLS = {
    'search_task_documents': '当前任务文档检索',
    'internet_search': 'Exa 网络搜索', 'list_sql_tables': '列出数据表',
    'get_table_data': '预览数据表', 'execute_sql_query': 'SQL 查询',
    'read_file_content': '读取任务附件', 'generate_markdown': '生成 Markdown',
    'convert_md_to_pdf': '转换 PDF',
}
