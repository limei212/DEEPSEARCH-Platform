"""文档检索助手的字典式配置，供上游示例引用。实际研搜使用管理平台的启用配置。"""

from app.agent.prompts import sub_agents_content
from app.tools.document_search_tool import search_task_documents

# 只检索当前任务的附件，索引由任务生命周期持有和释放。
knowledge_base_agent = {
    "name": sub_agents_content["documents"]["name"],
    "description": sub_agents_content["documents"]["description"],
    "system_prompt": sub_agents_content["documents"]["system_prompt"],
    "tools": [search_task_documents],
}
