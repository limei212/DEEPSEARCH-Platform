import { BranchesOutlined } from "@ant-design/icons";
import { Alert, App as AntApp } from "antd";
import { useEffect, useRef, useState } from "react";
import { useDeepAgentSession } from "../hooks/useDeepAgentSession";
import { useScrollFollow } from "../hooks/useScrollFollow";
import { createThreadId } from "../lib/thread";
import { restoreChatTurns } from '../lib/savedHistory';
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
  onHistoryRestored?: () => void;
}

export function ResearchWorkspace({
  workspaceId, isActive, selectedTaskId, onNewTask, onTaskSubmitted, onHistoryRestored
}: ResearchWorkspaceProps) {
  const { message } = AntApp.useApp();
  const [query, setQuery] = useState("");
  const [stagedItems, setStagedItems] = useState<UploadedItem[]>([]);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const follow = useScrollFollow<HTMLElement>(turns, isActive);
  const streamRef = follow.containerRef;
  const submittedFocusRef = useRef<string | null>(null);
  const submittingRef = useRef(false);
  const activeTurnIdRef = useRef<string | null>(null);
  const previousFocusRef = useRef<{ active: boolean; taskId: string | null }>({ active: false, taskId: null });
  const session = useDeepAgentSession(workspaceId);

  useEffect(() => {
    if (session.restoredTasks.length) {
      if (!submittingRef.current) activeTurnIdRef.current=session.restoredTasks.at(-1)!.id;
      setTurns(previous=>restoreChatTurns(session.restoredTasks,previous));
    }
    onHistoryRestored?.();
  }, [session.restoredTasks, onHistoryRestored]);

  useEffect(() => {
    const activeTurnId = activeTurnIdRef.current;
    if (!activeTurnId) return;
    setTurns((previous) => {
      return previous.map((turn) => turn.id === activeTurnId ? {
        ...turn, events: session.events, files: session.files,
        isRunning: session.isRunning, result: session.result
      } : turn);
    });
  }, [session.events, session.files, session.isRunning, session.result, session.restoredTasks]);

  useEffect(() => {
    const selectionChanged = !previousFocusRef.current.active || previousFocusRef.current.taskId !== selectedTaskId;
    const stream = streamRef.current;
    if (!isActive) {
      previousFocusRef.current.active = false;
      return;
    }
    if (!stream || !selectionChanged) return;

    const frame = window.requestAnimationFrame(() => {
      if (turns.length === 0) {
        follow.pauseFollow();
        stream.scrollTo({ top: 0 });
        if (selectedTaskId) return;
      } else if (selectedTaskId === submittedFocusRef.current) {
        submittedFocusRef.current = null;
        follow.resumeFollow();
        stream.scrollTo({ top: stream.scrollHeight });
      } else if (selectedTaskId) {
        const selectedTurn = stream.querySelector<HTMLElement>(`[data-task-id="${selectedTaskId}"]`);
        if (selectedTurn) {
          follow.pauseFollow();
          stream.scrollTo({
            top: selectedTurn.getBoundingClientRect().top - stream.getBoundingClientRect().top + stream.scrollTop,
            behavior: "auto"
          });
        } else return;
      }
      previousFocusRef.current = { active: true, taskId: selectedTaskId };
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
    follow.resumeFollow();
    submittedFocusRef.current = nextTurn.id;
    activeTurnIdRef.current = nextTurn.id;
    setTurns((previous) => [...previous, nextTurn]);
    setQuery("");
    onTaskSubmitted(nextTurn.id, workspaceId, content);
    try {
      await session.submitTask(content, nextTurn.id);
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
            正在思考
          </div>
        ) : null}
      </header>
      {session.lastError ? <Alert className="chat-alert" message={session.lastError} showIcon type="error" /> : null}
      <section className="chat-stream-panel" ref={streamRef} onScroll={follow.onScroll} onWheel={follow.onWheel} onKeyDown={follow.onKeyDown} onPointerDown={follow.pauseFollow} tabIndex={0} aria-label="研搜对话阅读区">
        <ConversationThread onUseExample={setQuery} turns={turns} onReadingHistory={follow.pauseFollow} parentFollowing={follow.isFollowing} />
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
