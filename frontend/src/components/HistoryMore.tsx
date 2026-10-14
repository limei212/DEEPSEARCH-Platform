import { useEffect, useRef } from 'react';
import { Button } from 'antd';

export function HistoryMore({loadMore, loading, error}: {loadMore:()=>void;loading:boolean;error:string}) {
  const sentinel=useRef<HTMLDivElement|null>(null);
  useEffect(()=>{
    const node=sentinel.current;
    if (!node || loading || error) return;
    const observer=new IntersectionObserver(entries=>{
      if (entries.some(entry=>entry.isIntersecting)) loadMore();
    },{root:node.closest('.chat-sidebar,.ant-drawer-body'),rootMargin:'80px'});
    observer.observe(node);
    return ()=>observer.disconnect();
  },[loadMore,loading,error]);
  return <div ref={sentinel} className="task-history-more"><Button type="text" size="small" loading={loading} onClick={loadMore}>{error?'重新加载':'加载更多任务'}</Button></div>;
}
