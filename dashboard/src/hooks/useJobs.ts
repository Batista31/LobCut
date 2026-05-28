import { useCallback, useEffect, useState } from 'react';
import { api, type Job } from '../api';

export function useJobs(limit = 50) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [polling, setPolling] = useState(false);

  const refresh = useCallback(async () => {
    setPolling(true);
    try {
      setJobs(await api.jobs(limit));
    } finally {
      setLoading(false);
      setPolling(false);
    }
  }, [limit]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => {
      void refresh();
    }, 5000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  return { jobs, loading, polling, refresh, setJobs };
}
