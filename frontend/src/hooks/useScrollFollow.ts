import { useEffect, useRef } from 'react';
import type { KeyboardEvent, UIEvent, WheelEvent } from 'react';
import { createScrollFollow } from '../lib/thinking';

export function useScrollFollow<T extends HTMLElement>(content: unknown, active = true, onReadingHistory?: () => void, parentFollowing?: () => boolean) {
  const containerRef = useRef<T | null>(null);
  const controller = useRef(createScrollFollow());
  const pauseFollow = () => {
    controller.current.pause();
    onReadingHistory?.();
  };
  const resumeFollow = () => controller.current.resume();

  useEffect(() => {
    if (!active) return;
    const frame = window.requestAnimationFrame(() => {
      if (containerRef.current) controller.current.advance(containerRef.current, parentFollowing?.() ?? true);
    });
    return () => window.cancelAnimationFrame(frame);
  }, [active, content]);

  const onScroll = (event: UIEvent<T>) => {
    if (!controller.current.onScroll(event.currentTarget)) onReadingHistory?.();
  };
  const onWheel = (event: WheelEvent<T>) => {
    if (event.deltaY < 0) pauseFollow();
  };
  const onKeyDown = (event: KeyboardEvent<T>) => {
    if (['ArrowUp', 'PageUp', 'Home'].includes(event.key)) pauseFollow();
  };
  return {containerRef, pauseFollow, resumeFollow, onScroll, onWheel, onKeyDown, isFollowing: () => controller.current.isFollowing()};
}
