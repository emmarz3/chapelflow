import { useEffect, useState } from "react";

export function localDateKey(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

export function useTodayDateKey() {
  const [today, setToday] = useState(() => localDateKey(new Date()));
  useEffect(() => {
    const now = new Date();
    const nextMidnight = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1).getTime();
    const timeout = window.setTimeout(() => setToday(localDateKey(new Date())), nextMidnight - now.getTime() + 25);
    return () => window.clearTimeout(timeout);
  }, [today]);
  return today;
}
