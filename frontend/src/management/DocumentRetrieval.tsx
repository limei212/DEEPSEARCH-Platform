import { Alert, Checkbox, Tag } from 'antd';
import type { AgentConfig } from './types';

export function DocumentRetrieval({agent,update}:{agent?:AgentConfig;update?:(patch:Partial<AgentConfig>)=>void}) {
  return <section className="settings-card settings-stack">
    <div className="settings-heading"><h3>当前附件，随问随查</h3><Tag color="green">内置文档检索</Tag></div>
    <p>上传 PDF、Word（DOCX）、TXT 或 Markdown，助手会检索相关原文，并注明文件名、页码或段落位置。</p>
    {agent && update && <Checkbox checked={agent.builtin_tools.includes('search_task_documents')} onChange={event=>update({
      builtin_tools:event.target.checked?Array.from(new Set([...agent.builtin_tools,'search_task_documents'])):agent.builtin_tools.filter(name=>name!=='search_task_documents'),
      knowledge:event.target.checked?[]:agent.knowledge
    })}>允许此助手检索当前会话附件</Checkbox>}
    <Alert type="info" showIcon message="上传附件保留，检索索引在任务结束后释放" description="再次查询会重新建立临时索引，不建立长期知识库或跨任务文档记忆。问答历史仍会保留。新建任务不会带入其他会话的附件。" />
    <p className="resource-meta">首次使用会自动准备本地中文检索模型。无需填写知识库地址或额外 API Key，也无需启动 Docker。</p>
    <p className="resource-meta">使用方法：返回对话 → 上传附件 → 发送问题。扫描 PDF 需要先转换为可提取文字的文档。</p>
  </section>;
}
