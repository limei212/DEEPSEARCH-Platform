export interface SidebarTask {
  id: string;
  workspaceId: string;
  content: string;
  title: string;
}

export interface TaskHistoryState {
  workspaceIds: string[];
  activeWorkspaceId: string;
  activeTaskId: string | null;
  tasks: SidebarTask[];
}

export type TaskHistoryAction =
  | { type: "new"; workspaceId: string }
  | { type: "submitted"; id: string; workspaceId: string; content: string }
  | { type: "select"; taskId: string };

export function taskTitle(query: string): string {
  return Array.from(query.trim()).slice(0, 8).join("");
}

export function createTaskHistory(workspaceId: string): TaskHistoryState {
  return { workspaceIds: [workspaceId], activeWorkspaceId: workspaceId, activeTaskId: null, tasks: [] };
}

export function taskHistoryReducer(state: TaskHistoryState, action: TaskHistoryAction): TaskHistoryState {
  switch (action.type) {
    case "new": {
      const sentWorkspaceIds = new Set(state.tasks.map((task) => task.workspaceId));
      return {
        ...state,
        workspaceIds: [...state.workspaceIds.filter((id) => sentWorkspaceIds.has(id)), action.workspaceId],
        activeWorkspaceId: action.workspaceId,
        activeTaskId: null
      };
    }
    case "submitted": {
      const content = action.content.trim();
      if (!content) return state;
      return {
        ...state,
        activeWorkspaceId: action.workspaceId,
        activeTaskId: action.id,
        tasks: [{ id: action.id, workspaceId: action.workspaceId, content, title: taskTitle(content) }, ...state.tasks]
      };
    }
    case "select": {
      const task = state.tasks.find((item) => item.id === action.taskId);
      return task ? { ...state, activeWorkspaceId: task.workspaceId, activeTaskId: task.id } : state;
    }
  }
}
