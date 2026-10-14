import assert from 'node:assert/strict';
import test from 'node:test';
import { createScrollFollow, getThinkingProgress } from '../src/lib/thinking.ts';

const events = (...names) => names.map(event => ({event}));

test('reading earlier content stays fixed when new events, files or answers arrive', () => {
  const follow = createScrollFollow();
  const node = {scrollTop:0, scrollHeight:1000, clientHeight:200};
  follow.advance(node);
  assert.equal(node.scrollTop, 800);
  node.scrollTop = 420;
  follow.onScroll(node);
  for (const height of [1100, 1300, 1900]) {
    node.scrollHeight = height;
    follow.advance(node);
    assert.equal(node.scrollTop, 420);
  }
});

test('scrolling back to the bottom resumes following new content', () => {
  const follow = createScrollFollow();
  const node = {scrollTop:100, scrollHeight:1000, clientHeight:200};
  follow.pause();
  follow.onScroll(node);
  follow.advance(node);
  assert.equal(node.scrollTop, 100);
  node.scrollTop = 800;
  follow.onScroll(node);
  node.scrollHeight = 1200;
  follow.advance(node);
  assert.equal(node.scrollTop, 1000);
});

test('upward wheel input cancels a pending follow even before the scroll event', () => {
  const follow = createScrollFollow();
  const node = {scrollTop:800, scrollHeight:1100, clientHeight:200};
  follow.pause();
  assert.equal(follow.advance(node), false);
  assert.equal(node.scrollTop, 800);
});

test('a newly submitted task can explicitly resume following', () => {
  const follow = createScrollFollow();
  const node = {scrollTop:120, scrollHeight:1100, clientHeight:200};
  follow.pause();
  follow.resume();
  follow.advance(node);
  assert.equal(node.scrollTop, 900);
});

test('reading the outer conversation also freezes the inner process timeline', () => {
  const outer = createScrollFollow();
  const inner = createScrollFollow();
  const node = {scrollTop:300, scrollHeight:600, clientHeight:200};
  outer.pause();
  inner.advance(node, outer.isFollowing());
  assert.equal(node.scrollTop, 300);
});

test('configuration events keep the understanding stage and routing advances it', () => {
  assert.equal(getThinkingProgress(events('session_created','agent_config')).stage, 0);
  assert.equal(getThinkingProgress(events('assistant_call','agent_config')).stage, 1);
});

test('parallel tools remain in dispatch until every tool has returned', () => {
  assert.equal(getThinkingProgress(events('tool_start','tool_start','tool_result')).stage, 1);
  assert.equal(getThinkingProgress(events('tool_start','tool_start','tool_result','tool_result')).stage, 2);
});

test('a follow-up search reactivates the dispatch arrow after synthesis', () => {
  assert.equal(getThinkingProgress(events('tool_start','tool_result','tool_start')).stage, 1);
  assert.equal(getThinkingProgress(events('tool_start','tool_result','tool_start','tool_error','output_validated')).stage, 2);
});

test('completion, cancellation and failure stop indicating running progress', () => {
  assert.equal(getThinkingProgress(events('task_result')).status, 'complete');
  assert.equal(getThinkingProgress(events('task_cancelled')).status, 'cancelled');
  assert.equal(getThinkingProgress(events('error')).status, 'error');
});
