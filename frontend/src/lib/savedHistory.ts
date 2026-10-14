import type { MonitorMessage, SavedTask } from '../types';
import type { ChatTurn } from '../components/ConversationThread';

export function mergeMonitorEvents(saved: MonitorMessage[], live: MonitorMessage[]): MonitorMessage[] {
  const events=new Map<string,MonitorMessage>();
  for (const event of [...saved,...live]) {
    const key=event.sequence!==undefined?`${event.task_id}:${event.sequence}`:JSON.stringify(event);
    events.set(key,event);
  }
  return Array.from(events.values()).sort((a,b)=>(a.sequence??0)-(b.sequence??0));
}

export function restoreChatTurns(saved: SavedTask[], live: ChatTurn[]): ChatTurn[] {
  const turns=new Map<string,ChatTurn>();
  for (const turn of saved) turns.set(turn.id,turn);
  for (const turn of live) {
    const stored=turns.get(turn.id);
    turns.set(turn.id,stored?{...stored,...turn,events:mergeMonitorEvents(stored.events,turn.events),
      result:turn.result||stored.result, files:turn.files.length?turn.files:stored.files,
      isRunning:stored.isRunning && turn.isRunning}:turn);
  }
  return Array.from(turns.values()).sort((a,b)=>a.timestamp.localeCompare(b.timestamp));
}
