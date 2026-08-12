import { useEffect, useRef, useState } from "react";
import { API_BASE } from "../lib/api";

export interface ActivityEvent {
  id: string;
  event_type: string;
  description: string;
  entity_type: string | null;
  entity_id: number | null;
  timestamp: string;
}

export function useActivityFeed() {
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const counterRef = useRef(0);

  useEffect(() => {
    const source = new EventSource(`${API_BASE}/events`);

    source.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.event_type === "heartbeat") return;

      counterRef.current += 1;
      const event: ActivityEvent = { id: `${Date.now()}-${counterRef.current}`, ...data };
      setEvents((prev) => [event, ...prev].slice(0, 20));
    };

    return () => source.close();
  }, []);

  return events;
}
