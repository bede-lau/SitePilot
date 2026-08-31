import { useCallback, useEffect, useRef, useState } from "react";

const BOTTOM_THRESHOLD_PX = 80;

/**
 * Keeps a scroll container pinned to the bottom while new content streams in — but only while the
 * user hasn't scrolled up to read something earlier. Re-run whenever the tracked `deps` change
 * (e.g. message count, streaming text length, card count).
 */
export function useAutoScroll<T extends HTMLElement>(deps: unknown[]) {
  const ref = useRef<T>(null);
  const [stick, setStick] = useState(true);

  const onScroll = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    setStick(distanceFromBottom < BOTTOM_THRESHOLD_PX);
  }, []);

  useEffect(() => {
    if (!stick) return;
    const el = ref.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
    // Intentionally re-runs only when the caller's tracked values change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  const scrollToBottom = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    setStick(true);
  }, []);

  return { ref, onScroll, stick, scrollToBottom };
}
