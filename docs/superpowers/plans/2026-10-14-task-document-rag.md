# 临时文档检索 Implementation Plan

> 执行方式：superpowers:executing-plans，在当前项目中逐项实施。用户已确认方案并明确要求修改与完整联调。

Goal: 用文档检索助手替换默认 RAGFlow 助手；上传附件保留，解析内容与向量索引仅在一次任务中存活。

Architecture: FastEmbed 的 BAAI/bge-small-zh-v1.5 在 CPU 中向量化；按模型 token 上限分块，用 NumPy 内存矩阵做余弦检索并补充关键词匹配。当前任务通过 ContextVar 持有索引，主助手与子助手共享；完成、失败和取消均释放。模型权重可以缓存，文档向量不持久化。

Tech stack: Python 3.12 / FastAPI / DeepAgents / FastEmbed / NumPy / pypdf / python-docx / React。

## 已确认的范围

- 支持 PDF 文本页、DOCX 段落与表格、UTF-8 TXT / Markdown；扫描 PDF 提示需要可提取文本。
- 保留 app/updated 中的原始附件，可在同一会话再次查询；新任务从附件重新创建索引。
- 不启动 Docker、Ollama、RAGFlow 或向量数据库服务。
- 问答与事件历史保持现有持久化；检索片段不是可跨任务搜索的知识库。
- 保留旧 Agent 配置版本及其他助手；旧默认 RAGFlow Agent 发布为文档检索助手，未使用默认资源退出当前页面。
- 后端模型缓存与数据库均不进入 GitHub / 源码 ZIP。

## Review focus

- 同名文件及并发任务隔离，上传目录之外的路径与符号链接拒绝。
- 无附件、空文档、扫描 PDF、损坏文档与模型下载失败给出可理解错误，禁止静默换成伪语义检索。
- DOCX 表格及 PDF 页码能引用；长文分块不能被模型 token 截断。
- 正常返回、异常、取消都会释放向量；后续任务不复用之前的索引。
- 上传附件在刷新后可见；重复查询无需重新上传，历史列表不丢失。

## Task 1: Document engine

Files: app/rag/documents.py, app/rag/session.py, app/tools/document_search_tool.py, tests/test_document_rag.py。

- [x] 写失败测试：四种格式提取、来源定位、token 分块、检索、文件边界、索引释放。
- [x] 实现 DocumentChunk、TaskDocumentIndex；注入 embedding 接口供离线测试，实际默认 FastEmbed。
- [x] 运行针对性测试，通过后安装锁定 FastEmbed 并下载实际中文模型，检查真实向量输出。

## Task 2: Lifecycle and migration

Files: app/agent/main_agent.py, app/management/runtime.py, app/management/store.py, app/management/models.py, app/prompt/prompts.yml, app/api/server.py。

- [x] 写失败测试：旧默认助手迁移幂等、保留历史版本、任务级索引隔离与释放、附件列表恢复。
- [x] 注册 search_task_documents 工具，创建每任务的索引作用域；助手测试也使用独立作用域。
- [x] 默认助手使用本地检索工具；模板提示词要求先检索后回答，并附文件名与定位。
- [x] 保留附件文件、恢复上传列表；每次任务独立执行上下文，避免旧检索片段成为新任务的隐式文档记忆。

## Task 3: UI and docs

Files: frontend/src/management/DocumentRetrieval.tsx, AgentEditor.tsx, ResourceCenter.tsx, ConversationThread.tsx, hooks/useDeepAgentSession.ts, README.md, .env.example。

- [x] 文档检索页展示内置开关、格式、生命周期、引用行为；Skills / MCP 页保持可配置。
- [x] 示例提示先上传白皮书；资源中心展示内置检索说明，不再新增默认 RAGFlow 连接。
- [x] 更新依赖锁、README 与操作说明；前端测试和生产构建通过。

## Task 4: Full verification

- [x] 执行全部后端 / 前端测试。
- [x] 生成不含用户资料的测试 PDF、DOCX 表格、TXT、Markdown；真实模型验证检索定位。
- [x] 真实 HTTP 上传 -> 主 Agent -> 文档助手 -> 检索 -> DeepSeek 答案；检查引用与工具调用。
- [x] 刷新、重复查询、重启后从保留附件再次查询，确认新索引并在终态清理；截图。
- [x] 更新可下载源码包，不将参考项目中的 .env、文档或密钥复制到源码中。

实际结果见 docs/文档检索联调结果.txt。
