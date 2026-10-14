export interface SidebarTask {
  id: string;
  workspaceId: string;
  content: string;
  title: string;
  timestamp?: string;
  status?: string;
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
// Restore pages independently of mounted chat workspaces.
export type RestoredHistoryAction = { type: "restore"; tasks: SidebarTask[]; selectedTaskId?: string };

export function taskTitle(query: string): string {
  return Array.from(query.trim()).slice(0, 8).join("");
}

export function createTaskHistory(workspaceId: string): TaskHistoryState {
  return { workspaceIds: [workspaceId], activeWorkspaceId: workspaceId, activeTaskId: null, tasks: [] };
}

export function taskHistoryReducer(state: TaskHistoryState, action: TaskHistoryAction | RestoredHistoryAction): TaskHistoryState {
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
        tasks: [{ id: action.id, workspaceId: action.workspaceId, content, title: taskTitle(content), timestamp: new Date().toISOString() }, ...state.tasks.filter(task=>task.id!==action.id)]
      };
    }
    case "select": {
      const task = state.tasks.find((item) => item.id === action.taskId);
      return task ? { ...state, workspaceIds: Array.from(new Set([...state.workspaceIds, task.workspaceId])), activeWorkspaceId: task.workspaceId, activeTaskId: task.id } : state;
    }
    case "restore": {
      const tasks=Array.from(new Map([...action.tasks,...state.tasks].map(task=>[task.id,task])).values());
      tasks.sort((a,b)=>(b.timestamp||'').localeCompare(a.timestamp||''));
      const selected=tasks.find(task=>task.id===action.selectedTaskId);
      return {...state,tasks,...(selected?{
        workspaceIds:Array.from(new Set([...state.workspaceIds,selected.workspaceId])),
        activeWorkspaceId:selected.workspaceId,activeTaskId:selected.id
      }:{})};
    }
  }
}
