export type ConnectionState = "connecting" | "connected" | "reconnecting" | "closed";

export type MonitorEventName =
  | "session_created"
  | "tool_start"
  | "assistant_call"
  | "task_result"
  | "task_cancelled"
  | "error"
  | string;

export interface MonitorMessage {
  type: "monitor_event";
  event: MonitorEventName;
  message: string;
  data: Record<string, unknown>;
  timestamp: string;
  task_id?: string;
  sequence?: number;
}

export interface PongMessage {
  type: "pong";
  message: string;
}

export interface SavedTask {
  id: string;
  workspaceId: string;
  content: string;
  title: string;
  timestamp: string;
  status: string;
  result: string;
  events: MonitorMessage[];
  files: OutputFile[];
  isRunning: boolean;
  sessionPath: string;
}

export type SocketMessage = MonitorMessage | PongMessage | {type:"history";tasks:SavedTask[]};

export interface TaskResponse {
  status: "started" | string;
  thread_id: string;
  task_id?: string;
}

export interface CancelTaskResponse {
  status: "cancelled" | "cancelling" | string;
  thread_id: string;
  message?: string;
}

export interface UploadResponse {
  status: "uploaded" | string;
  files: string[];
}

export interface OutputFile {
  name: string;
  type: "file" | string;
  path: string;
  size: number;
  mtime: number;
}

export interface FileListResponse {
  files?: OutputFile[];
  error?: string;
}

export interface UploadedItem {
  uid: string;
  name: string;
  size: number;
  raw?: File;
}
