"""Exa 联网搜索，保留 internet_search 的助手调用接口。"""

import os
from pathlib import Path
from typing import Annotated, Literal

import httpx
from dotenv import load_dotenv
from langchain_core.tools import tool
from pydantic import Field

from app.api.monitor import monitor

load_dotenv(Path(__file__).resolve().parents[2] / '.env')


@tool
def internet_search(
    query: str,
    topic: Literal['news', 'finance', 'general'] = 'general',
    max_results: Annotated[int, Field(ge=1, le=20)] = 5,
    include_raw_content: bool = False,
) -> dict:
    """使用 Exa 检索互联网公开信息，返回标题、来源链接、发布日期和摘录。

    query 是搜索问题；topic=news 限定新闻，finance/general 按原问题通用检索。
    max_results 为 1–20，默认 5；include_raw_content=True 额外获取每页最多
    12000 字符的正文。此工具不查询私有知识库或业务数据库。
    """
    query = query.strip()
    if not query:
        raise ValueError('搜索问题不能为空')
    key = os.getenv('EXA_API_KEY', '').strip()
    if not key or any(marker in key.lower() for marker in ['placeholder', 'your_', 'your-', 'replace', '你的', 'changeme']):
        raise ValueError('尚未配置可用的 EXA_API_KEY，请填写项目 .env')

    contents = {'highlights': True}
    if include_raw_content:
        contents['text'] = {'maxCharacters': 12000}
    payload = {'query': query, 'type': 'auto', 'numResults': max_results, 'contents': contents}
    if topic == 'news':
        payload['category'] = 'news'
    # 财经并不等于财报，避免把原 finance 调用缩窄为 financial report 类别。
    monitor.report_tool('Exa 网络搜索', args={'query': query, 'topic': topic, 'max_results': max_results, 'include_raw_content': include_raw_content})
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post('https://api.exa.ai/search', headers={'x-api-key': key}, json=payload)
    except httpx.TimeoutException:
        raise ValueError('Exa 搜索超时，请稍后重试') from None
    except httpx.RequestError:
        raise ValueError('无法连接 Exa 搜索服务，请检查网络连接') from None

    if response.status_code in (401, 403):
        raise ValueError('Exa 认证失败，请检查 EXA_API_KEY 和账号权限')
    if response.status_code == 402:
        raise ValueError('Exa 额度不足，请检查账号余额')
    if response.status_code == 429:
        raise ValueError('Exa 请求频率受限，请稍后重试')
    if not response.is_success:
        raise ValueError(f'Exa 搜索失败（HTTP {response.status_code}）')
    try:
        data = response.json()
    except ValueError:
        raise ValueError('Exa 返回了无法解析的搜索结果') from None
    if not isinstance(data, dict) or not isinstance(data.get('results'), list):
        raise ValueError('Exa 搜索结果格式异常')

    results = []
    for item in data['results']:
        if not isinstance(item, dict) or not item.get('url'):
            continue
        highlights = item.get('highlights') or []
        excerpt = '\n'.join(value for value in highlights if isinstance(value, str))
        result = {'title': item.get('title') or item['url'], 'url': item['url'],
                  'content': excerpt or item.get('summary') or item.get('text') or '',
                  'published_date': item.get('publishedDate'), 'author': item.get('author')}
        if include_raw_content:
            result['raw_content'] = item.get('text') or ''
        results.append(result)
    return {'provider': 'exa', 'query': query, 'results': results, 'request_id': data.get('requestId')}


if __name__ == '__main__':
    from pprint import pprint
    pprint(internet_search.invoke({'query': '跨境电商 AI 客服趋势'}))
