import { BranchesOutlined } from "@ant-design/icons";
import { Alert, App as AntApp } from "antd";
import { useEffect, useRef, useState } from "react";
import { useDeepAgentSession } from "../hooks/useDeepAgentSession";
import { createThreadId } from "../lib/thread";
import type { UploadedItem } from "../types";
import { ChatComposer } from "./ChatComposer";
import { ConversationThread } from "./ConversationThread";
import type { ChatTurn } from "./ConversationThread";

interface ResearchWorkspaceProps {
  workspaceId: string;
  isActive: boolean;
  selectedTaskId: string | null;
  onNewTask: () => void;
  onTaskSubmitted: (id: string, workspaceId: string, content: string) => void;
}

export function ResearchWorkspace({
  workspaceId, isActive, selectedTaskId, onNewTask, onTaskSubmitted
}: ResearchWorkspaceProps) {
  const { message } = AntApp.useApp();
  const [query, setQuery] = useState("");
  const [stagedItems, setStagedItems] = useState<UploadedItem[]>([]);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const streamRef = useRef<HTMLElement | null>(null);
  const submittingRef = useRef(false);
  const activeTurnIdRef = useRef<string | null>(null);
  const previousFocusRef = useRef<{ active: boolean; taskId: string | null }>({ active: false, taskId: null });
  const session = useDeepAgentSession(workspaceId);

  useEffect(() => {
    const activeTurnId = activeTurnIdRef.current;
    if (!activeTurnId) return;
    setTurns((previous) => {
      return previous.map((turn) => turn.id === activeTurnId ? {
        ...turn, events: session.events, files: session.files,
        isRunning: session.isRunning, result: session.result
      } : turn);
    });
  }, [session.events, session.files, session.isRunning, session.result]);

  useEffect(() => {
    const selectionChanged = !previousFocusRef.current.active || previousFocusRef.current.taskId !== selectedTaskId;
    previousFocusRef.current = { active: isActive, taskId: selectedTaskId };
    const stream = streamRef.current;
    if (!isActive || !stream) return;

    const frame = window.requestAnimationFrame(() => {
      if (turns.length === 0) {
        stream.scrollTo({ top: 0 });
        return;
      }
      if (selectionChanged && selectedTaskId) {
        const selectedTurn = stream.querySelector<HTMLElement>(`[data-task-id="${selectedTaskId}"]`);
        if (selectedTurn) {
          stream.scrollTo({
            top: selectedTurn.getBoundingClientRect().top - stream.getBoundingClientRect().top + stream.scrollTop,
            behavior: "smooth"
          });
          return;
        }
      }
      if (!selectedTaskId || selectedTaskId === turns[turns.length - 1]?.id) {
        stream.scrollTo({ top: stream.scrollHeight, behavior: "smooth" });
      }
    });
    return () => window.cancelAnimationFrame(frame);
  }, [isActive, selectedTaskId, turns]);

  async function handleSubmit() {
    if (submittingRef.current || session.isRunning || session.isUploading) return;
    const content = query.trim();
    if (!content) {
      message.warning("请输入研搜任务");
      return;
    }
    const nextTurn: ChatTurn = {
      id: createThreadId(), content, events: [], files: [], isRunning: true,
      result: "", timestamp: new Date().toISOString()
    };
    submittingRef.current = true;
    activeTurnIdRef.current = nextTurn.id;
    setTurns((previous) => [...previous, nextTurn]);
    setQuery("");
    onTaskSubmitted(nextTurn.id, workspaceId, content);
    try {
      await session.submitTask(content);
      message.success("任务已启动，执行过程会显示在对话中");
    } catch (error) {
      activeTurnIdRef.current = null;
      const errorMessage = error instanceof Error ? error.message : "任务启动失败";
      setTurns((previous) => previous.map((turn) => turn.id === nextTurn.id
        ? { ...turn, isRunning: false, result: errorMessage } : turn));
      message.error(errorMessage);
    } finally {
      submittingRef.current = false;
    }
  }

  async function handleCancel() {
    try {
      const response = await session.cancelCurrentTask();
      message.info(response.status === "cancelling" ? "取消请求已发送，正在等待当前调用结束" : "任务已取消");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "取消任务失败");
    }
  }

  async function handleUpload(items: UploadedItem[]) {
    try {
      const response = await session.uploadFiles(items);
      setStagedItems([]);
      message.success(`已上传 ${response.files.length} 个文件`);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "上传失败");
    }
  }

  return (
    <main className="chat-main" style={isActive ? undefined : { display: "none" }} aria-hidden={!isActive}>
      <header className="chat-topbar">
        <div>
          <span className="panel-kicker">CHAT WORKSPACE</span>
        </div>
        {session.isRunning ? (
          <div className="run-indicator run-indicator--live">
            <BranchesOutlined aria-hidden />
            研搜中
          </div>
        ) : null}
      </header>
      {session.lastError ? <Alert className="chat-alert" message={session.lastError} showIcon type="error" /> : null}
      <section className="chat-stream-panel" ref={streamRef}>
        <ConversationThread onUseExample={setQuery} turns={turns} />
      </section>
      <ChatComposer
        isCancelling={session.isCancelling} isRunning={session.isRunning} isUploading={session.isUploading}
        onCancel={handleCancel} onNewSession={onNewTask} onQueryChange={setQuery}
        onStagedItemsChange={setStagedItems} onSubmit={handleSubmit} onUpload={handleUpload}
        query={query} stagedItems={stagedItems} uploadedItems={session.uploadedItems}
      />
    </main>
  );
}
