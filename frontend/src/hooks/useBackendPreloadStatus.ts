import { useEffect, useState } from 'react';

const HEALTH_URL = 'http://127.0.0.1:8000/health';

interface HealthResponse {
  status?: string;
  completed?: number;
  total?: number;
  detail?: string | null;
  eta_seconds?: number | null;
}

export interface BackendPreloadStatus {
  loading: boolean;
  fraction?: number;
  detail?: string | null;
  etaSeconds?: number | null;
}

const initialStatus: BackendPreloadStatus = { loading: true };

export default function useBackendPreloadStatus(): BackendPreloadStatus {
  const [status, setStatus] = useState<BackendPreloadStatus>(initialStatus);

  useEffect(() => {
    let active = true;

    const poll = async () => {
      try {
        const response = await fetch(HEALTH_URL);
        if (!response.ok) return;
        const health = await response.json() as HealthResponse;
        if (!active) return;

        const total = health.total ?? 0;
        setStatus({
          loading: health.status !== 'ready',
          fraction: total > 0 ? (health.completed ?? 0) / total : undefined,
          detail: health.detail,
          etaSeconds: health.eta_seconds,
        });
      } catch {
        // The server has not opened its health endpoint yet. Keep the previous
        // status visible and retry; this avoids replacing useful progress with
        // a transient network error during a restart.
      }
    };

    void poll();
    const intervalId = window.setInterval(() => void poll(), 500);
    return () => {
      active = false;
      window.clearInterval(intervalId);
    };
  }, []);

  return status;
}
