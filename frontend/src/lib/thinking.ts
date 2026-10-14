interface ScrollContainer {
  scrollTop: number;
  scrollHeight: number;
  clientHeight: number;
}

export function createScrollFollow() {
  let following = true;
  let previousTop = 0;
  return {
    pause() { following = false; },
    resume() { following = true; },
    isFollowing() { return following; },
    onScroll(node: ScrollContainer) {
      const atBottom = node.scrollHeight - node.clientHeight - node.scrollTop <= 2;
      if (atBottom) following = true;
      else if (node.scrollTop < previousTop - 1) following = false;
      previousTop = node.scrollTop;
      return following;
    },
    advance(node: ScrollContainer, parentFollowing = true) {
      if (!following || !parentFollowing) return false;
      node.scrollTop = Math.max(0, node.scrollHeight - node.clientHeight);
      previousTop = node.scrollTop;
      return true;
    },
  };
}

export function getThinkingProgress(events: ReadonlyArray<{event: string}>) {
  let stage = 0;
  let pending = 0;
  let status: 'running' | 'complete' | 'cancelled' | 'error' = 'running';
  for (const {event} of events) {
    if (status !== 'running') break;
    if (event === 'assistant_call') stage = 1;
    if (event === 'tool_start') { pending += 1; stage = 1; }
    if (event === 'tool_result' || event === 'tool_error') {
      pending = Math.max(0, pending - 1);
      stage = pending > 0 ? 1 : 2;
    }
    if (event === 'output_validated') stage = 2;
    if (event === 'task_result') { stage = 2; status = 'complete'; }
    if (event === 'task_cancelled') status = 'cancelled';
    if (event === 'error') status = 'error';
  }
  return {stage, status};
}
