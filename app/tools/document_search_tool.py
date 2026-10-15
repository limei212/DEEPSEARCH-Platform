import json
from langchain_core.tools import tool
from app.api.monitor import monitor
from app.rag.session import current_index


@tool
async def search_task_documents(question:str,limit:int=5,filename:str='')->str:
    """检索当前任务已上传的 PDF、DOCX、TXT、Markdown 文档，返回相关原文片段、文件名、页码或段落。question 为具体检索问题；filename 可限定一个附件，留空检索全部当前附件。"""
    monitor.report_tool('search_task_documents',{'question':question,'filename':filename,'limit':limit})
    index=current_index.get()
    if index is None:raise ValueError('文档检索只能在当前任务内执行，请先上传附件并启动任务')
    result=await index.search(question,limit,filename)
    return json.dumps(result,ensure_ascii=False)
