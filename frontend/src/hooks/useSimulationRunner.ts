import { useCallback, useEffect, useRef, useState } from 'react';

export interface RunTimelineOptions<TFrame> {
  fromDate: string;
  toDate: string;
  framesByDate: Record<string, TFrame>;
  eachDay: (fromDate: string, toDate: string) => string[];
  onFrame: (date: string, frame: TFrame) => void;
  onStart?: (framesByDate: Record<string, TFrame>) => void;
  onComplete?: () => void;
  onNoFrames?: () => void;
}

export interface UseSimulationRunnerOptions {
  intervalMs?: number;
}

export interface UseSimulationRunnerReturn {
  isRunning: boolean;
  stop: () => void;
  runTimeline: <TFrame>(options: RunTimelineOptions<TFrame>) => string[];
}

/**
 * Plays a date-keyed simulation result over time. Mirrors the timeline behavior
 * currently in SimulationPage and guarantees interval cleanup on unmount.
 */
export function useSimulationRunner({ intervalMs = 1000 }: UseSimulationRunnerOptions = {}): UseSimulationRunnerReturn {
  const [isRunning, setIsRunning] = useState(false);
  const timerRef = useRef<number | null>(null);

  const stop = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setIsRunning(false);
  }, []);

  useEffect(() => stop, [stop]);

  const runTimeline = useCallback(
    <TFrame>({
      fromDate,
      toDate,
      framesByDate,
      eachDay,
      onFrame,
      onStart,
      onComplete,
      onNoFrames,
    }: RunTimelineOptions<TFrame>): string[] => {
      const timeline = eachDay(fromDate, toDate).filter(
        (date) => framesByDate[date] !== undefined,
      );

      if (timeline.length === 0) {
        stop();
        onNoFrames?.();
        return timeline;
      }

      stop();
      onStart?.(framesByDate);

      let cursor = 0;
      onFrame(timeline[0], framesByDate[timeline[0]]);

      timerRef.current = window.setInterval(() => {
        cursor += 1;
        if (cursor >= timeline.length) {
          stop();
          onComplete?.();
          return;
        }

        const date = timeline[cursor];
        onFrame(date, framesByDate[date]);
      }, intervalMs);

      setIsRunning(true);
      return timeline;
    },
    [intervalMs, stop],
  );

  return {
    isRunning,
    stop,
    runTimeline,
  };
}

export default useSimulationRunner;
