import { useEffect, useState } from 'react';
import { api, type Job, type User } from '../api';
import { JobDetail } from '../components/JobDetail';
import { JobsTable } from '../components/JobsTable';
import { StatsBar } from '../components/StatsBar';
import { Topbar } from '../components/Topbar';
import { useJobs } from '../hooks/useJobs';
import { routeHref } from '../navigation';

type Props = {
  user: User;
};

export function Dashboard({ user }: Props) {
  const [selected, setSelected] = useState<Job | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const { jobs, loading, polling, refresh, setJobs } = useJobs();

  const showToast = (message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(null), 3000);
  };

  return (
    <main className="appShell">
      <Topbar user={user} currentPath="/" />
      <StatsBar jobs={jobs} polling={polling} />
      <JobsTable
        jobs={jobs}
        loading={loading}
        polling={polling}
        refresh={refresh}
        onDeleteLocal={(jobId) => {
          setJobs((current) => current.filter((job) => job.id !== jobId));
          if (selected?.id === jobId) {
            setSelected(null);
          }
        }}
        onToast={showToast}
        onSelect={setSelected}
        selectedId={selected?.id ?? null}
      />
      <JobDetail job={selected} onClose={() => setSelected(null)} />
      {toast ? <div className="toastBanner">{toast}</div> : null}
    </main>
  );
}
