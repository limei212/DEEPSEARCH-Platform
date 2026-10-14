import assert from 'node:assert/strict';
import test from 'node:test';
import { mergeMonitorEvents,restoreChatTurns } from '../src/lib/savedHistory.ts';

test('websocket replay preserves all events while deduplicating already received sequences',()=>{
  const saved=Array.from({length:150},(_,i)=>({sequence:i+1,task_id:'a',event:'tool_start',timestamp:'2026-10-14',message:'event',data:{}}));
  const live=[saved[149],{...saved[149],sequence:151,event:'task_result'}];
  const merged=mergeMonitorEvents(saved,live);
  assert.equal(merged.length,151);
  assert.equal(merged[0].sequence,1);
  assert.equal(merged.at(-1).event,'task_result');
});

test('restored turns retain answers and do not overwrite a newly submitted turn',()=>{
  const stored={id:'old',content:'原始问题',timestamp:'2026-10-14T10:00:00Z',events:[],files:[],result:'原始答案',isRunning:false};
  const pending={id:'new',content:'新问题',timestamp:'2026-10-14T11:00:00Z',events:[],files:[],result:'',isRunning:true};
  const restored=restoreChatTurns([stored],[pending]);
  assert.equal(restored.length,2);
  assert.equal(restored[0].result,'原始答案');
  assert.equal(restored[1].isRunning,true);
});
