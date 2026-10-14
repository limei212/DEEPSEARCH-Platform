import {
  CloudServerOutlined,
  DatabaseOutlined,
  FileSearchOutlined,
  FileTextOutlined,
  MenuOutlined,
  PlusOutlined,
  SettingOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { Button, Drawer, Input, Modal, Select } from "antd";
import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { HistoryMore } from './components/HistoryMore';
import { getSavedTask, listTaskHistory } from './lib/api';
import { ResearchWorkspace } from "./components/ResearchWorkspace";
import { createTaskHistory, taskHistoryReducer } from "./lib/taskHistory";
import { createThreadId } from "./lib/thread";
import { AgentEditor } from "./management/AgentEditor";
import { ResourceCenter } from "./management/ResourceCenter";
import { getCatalog } from "./management/api";
import { newAgent, statusLabels } from "./management/types";
import type { AgentConfig, Catalog } from "./management/types";
import "./management/management.css";

type View =
  | { kind: "chat" }
  | { kind: "agent"; id: string | null }
  | { kind: "resources" };
const icons = {
  research: <CloudServerOutlined />,
  database: <DatabaseOutlined />,
  knowledge: <FileSearchOutlined />,
  spark: <ThunderboltOutlined />,
};

export default function App() {
  const [history, dispatch] = useReducer(taskHistoryReducer, undefined, () =>
    createTaskHistory(createThreadId()),
  );
  const [catalog, setCatalog] = useState<Catalog>({
    agents: [],
    resources: [],
    builtin_tools: [],
  });
  const [loadError, setLoadError] = useState("");
  const [view, setView] = useState<View>({ kind: "chat" });
  const [dirty, setDirty] = useState(false);
  const [mobileMenu, setMobileMenu] = useState(false);
  const [creating, setCreating] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState('');
  const [nextCursor, setNextCursor] = useState<number|null>(null);
  const historyInitialized=useRef(false);
  const historyLoadingRef=useRef(false);
  const refreshHistory=useCallback(async()=>{
    if (historyLoadingRef.current) return;
    historyLoadingRef.current=true;
    setHistoryLoading(true);
    try {
      const page=await listTaskHistory();
      let selectedTaskId: string|undefined;
      if (!historyInitialized.current) {
        const selected=localStorage.getItem('deepsearch-active-task');
        if (selected) {
          selectedTaskId=selected;
          if (!page.tasks.some(task=>task.id===selected)) {
            try {page.tasks.unshift(await getSavedTask(selected));} catch {selectedTaskId=undefined;}
          }
        }
        setNextCursor(page.next_cursor);
        historyInitialized.current=true;
      }
      dispatch({type:'restore',tasks:page.tasks,selectedTaskId});
      setHistoryError('');
    } catch(error) {
      setHistoryError(error instanceof Error?error.message:'无法读取任务历史');
    } finally {historyLoadingRef.current=false;setHistoryLoading(false);}
  },[]);
  const loadMoreHistory=useCallback(async()=>{
    if (nextCursor===null || historyLoadingRef.current) return;
    historyLoadingRef.current=true;
    setHistoryLoading(true);
    try {
      const page=await listTaskHistory(nextCursor);
      dispatch({type:'restore',tasks:page.tasks});
      setNextCursor(page.next_cursor);
      setHistoryError('');
    } catch(error) {setHistoryError(error instanceof Error?error.message:'无法读取任务历史');}
    finally {historyLoadingRef.current=false;setHistoryLoading(false);}
  },[nextCursor]);
  useEffect(()=>{void refreshHistory();},[refreshHistory]);
  const [template, setTemplate] = useState("blank");
  const [newName, setNewName] = useState("");
  const [draft, setDraft] = useState<AgentConfig>(newAgent);
  const [draftKey, setDraftKey] = useState(0);
  const refresh = useCallback(async () => {
    try {
      setCatalog(await getCatalog());
      setLoadError("");
    } catch (error) {
      setLoadError(
        error instanceof Error
          ? error.message
          : "无法读取助手配置，请检查后端服务",
      );
    }
  }, []);
  useEffect(() => {
    void refresh();
  }, [refresh]);
  useEffect(() => {
    if (!dirty) return;
    const leave = (event: BeforeUnloadEvent) => {
      event.preventDefault();
    };
    window.addEventListener("beforeunload", leave);
    return () => window.removeEventListener("beforeunload", leave);
  }, [dirty]);
  function navigate(next: View, action?: () => void) {
    const go = () => {
      setDirty(false);
      setView(next);
      setMobileMenu(false);
      action?.();
    };
    if (dirty)
      Modal.confirm({
        title: "离开前保存修改吗？",
        content:
          "当前草稿有未保存的修改。可取消返回详情页保存，或放弃修改并继续。",
        okText: "放弃并继续",
        cancelText: "返回编辑",
        onOk: go,
      });
    else go();
  }
  function handleNewTask() {
    navigate({ kind: "chat" }, () => {
      localStorage.removeItem('deepsearch-active-task');
      dispatch({ type: "new", workspaceId: createThreadId() });
    });
  }
  function openCreate(copyId?: string) {
    setTemplate(copyId || "blank");
    setNewName("");
    setMobileMenu(false);
    setCreating(true);
  }
  function createDraft() {
    const source = catalog.agents.find((agent) => agent.id === template);
    const next = newAgent(source);
    if (newName.trim()) next.name = newName.trim();
    navigate({ kind: "agent", id: null }, () => {
      setDraft(next);
      setDraftKey((value) => value + 1);
      setCreating(false);
    });
  }
  const selected =
    view.kind === "agent"
      ? view.id
        ? catalog.agents.find((agent) => agent.id === view.id)
        : draft
      : undefined;
  const sidebar = (
    <>
      <div className="sidebar-brand">
        <h1 className="sidebar-brand-title">DEEPSEARCH</h1>
        <p>对话式多智能体研究台</p>
      </div>
      <Button className="new-chat-button" block onClick={handleNewTask}>
        新建任务
      </Button>
      <div className="sidebar-section sidebar-agents">
        <div className="sidebar-section-heading">
          <span className="sidebar-label">AGENTS</span>
          <Button
            aria-label="添加 Agent"
            size="small"
            type="text"
            icon={<PlusOutlined />}
            onClick={() => openCreate()}
          />
        </div>
        <ul className="agent-navigation-list">
          {catalog.agents.map((agent) => (
            <li key={agent.id}>
              <button
                type="button"
                className={`agent-navigation-button ${view.kind === "agent" && view.id === agent.id ? "agent-navigation-button--active" : ""}`}
                onClick={() => navigate({ kind: "agent", id: agent.id })}
                title={agent.description}
              >
                {icons[agent.icon]}
                <span className="agent-navigation-name">{agent.name}</span>
                <span
                  className={`agent-navigation-status agent-navigation-status--${agent.status}`}
                >
                  {statusLabels[agent.status || "draft"]}
                </span>
              </button>
            </li>
          ))}
        </ul>
        {loadError && (
          <div className="sidebar-load-error">
            {loadError}
            <Button type="link" size="small" onClick={() => void refresh()}>
              重新载入
            </Button>
          </div>
        )}
        <Button
          className="sidebar-resources-button"
          type="text"
          icon={<SettingOutlined />}
          onClick={() => navigate({ kind: "resources" })}
        >
          管理连接资源
        </Button>
      </div>
      <nav className="sidebar-section sidebar-tasks" aria-label="任务列表">
        <span className="sidebar-label">任务列表</span>
        {history.tasks.length === 0 ? (
          <p className="task-history-empty">{historyLoading?'正在读取历史任务':'暂无任务'}</p>
        ) : (
          <ul className="task-history-list">
            {history.tasks.map((task) => (
              <li key={task.id}>
                <button
                  type="button"
                  className={`task-history-button ${view.kind === "chat" && history.activeTaskId === task.id ? "task-history-button--active" : ""}`}
                  aria-current={
                    view.kind === "chat" && history.activeTaskId === task.id
                      ? "page"
                      : undefined
                  }
                  title={task.content}
                  onClick={() =>
                    navigate({ kind: "chat" }, () => {
                      localStorage.setItem('deepsearch-active-task',task.id);
                      dispatch({ type: "select", taskId: task.id });
                    })
                  }
                >
                  <FileTextOutlined aria-hidden />
                  <span>{task.title}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
        {historyError && <div className="sidebar-load-error">读取任务历史失败：{historyError}<Button type="link" size="small" onClick={()=>void refreshHistory()}>重试</Button></div>}
        {nextCursor!==null && <HistoryMore loadMore={()=>void loadMoreHistory()} loading={historyLoading} error={historyError} />}
      </nav>
    </>
  );
  return (
    <div className="chat-app-shell min-h-dvh">
      <aside className="chat-sidebar" aria-label="任务导航">
        {sidebar}
      </aside>
      <Button
        className="mobile-menu-button"
        aria-label="打开任务导航"
        icon={<MenuOutlined />}
        onClick={() => setMobileMenu(true)}
      />
      <Drawer
        title="任务与助手"
        open={mobileMenu}
        width={292}
        placement="left"
        onClose={() => setMobileMenu(false)}
      >
        <div className="mobile-sidebar-content">{sidebar}</div>
      </Drawer>
      {history.workspaceIds.map((workspaceId) => (
        <ResearchWorkspace
          key={workspaceId}
          workspaceId={workspaceId}
          isActive={
            view.kind === "chat" && history.activeWorkspaceId === workspaceId
          }
          selectedTaskId={
            history.activeWorkspaceId === workspaceId
              ? history.activeTaskId
              : null
          }
          onNewTask={handleNewTask}
          onHistoryRestored={refreshHistory}
          onTaskSubmitted={(id, workspaceId, content) => {
            localStorage.setItem('deepsearch-active-task',id);
            dispatch({ type: "submitted", id, workspaceId, content });
          }}
        />
      ))}
      {view.kind === "agent" && selected && (
        <AgentEditor
          key={selected.id || "new-" + draftKey}
          initial={selected}
          catalog={catalog}
          onDirty={setDirty}
          onRefresh={refresh}
          onBack={() => navigate({ kind: "chat" })}
          onCopy={() => openCreate(selected.id || undefined)}
          onSaved={async (agent) => {
            await refresh();
            setView({ kind: "agent", id: agent.id });
          }}
        />
      )}
      {view.kind === "resources" && (
        <ResourceCenter
          resources={catalog.resources}
          onRefresh={refresh}
          onBack={() => navigate({ kind: "chat" })}
        />
      )}
      <Modal
        title="添加一个助手"
        open={creating}
        okText="进入配置"
        cancelText="取消"
        onCancel={() => setCreating(false)}
        onOk={createDraft}
      >
        <div className="create-agent-template">
          <label className="form-label">
            创建方式
            <Select
              aria-label="创建方式"
              value={template}
              onChange={setTemplate}
              options={[
                { value: "blank", label: "空白助手" },
                ...catalog.agents.map((agent) => ({
                  value: agent.id!,
                  label: "复制 / 模板：" + agent.name,
                })),
              ]}
            />
          </label>
          <label className="form-label">
            助手名称
            <Input
              aria-label="新助手名称"
              value={newName}
              placeholder="例如 品类策略助手"
              onChange={(e) => setNewName(e.target.value)}
            />
          </label>
          <p className="resource-meta">
            创建后完善提示词、输入输出与资源连接，再测试并启用。
          </p>
        </div>
      </Modal>
    </div>
  );
}
