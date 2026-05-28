import { useEffect, useState } from 'react';
import { api, type Job, type User } from '../api';
import { JobDetail } from '../components/JobDetail';
import { JobsTable } from '../components/JobsTable';
import { StatsBar } from '../components/StatsBar';
import { Topbar } from '../components/Topbar';
import { useJobs } from '../hooks/useJobs';
import { routeHref } from '../navigation';

const PAGE_SIZE = 50;

type Props = {
  user: User;
};

export function Dashboard({ user }: Props) {
  const [selected, setSelected] = useState<Job | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [jobLimit, setJobLimit] = useState(PAGE_SIZE);
  const { jobs, loading, polling, refresh, setJobs } = useJobs(jobLimit);

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
          if (selected?.id === jobId) setSelected(null);
        }}
        onToast={showToast}
        onSelect={setSelected}
        selectedId={selected?.id ?? null}
      />
      <JobDetail
        job={selected}
        onClose={() => setSelected(null)}
        onDelete={(jobId) => {
          setJobs((current) => current.filter((j) => j.id !== jobId));
          setSelected(null);
        }}
      />
      {jobs.length >= jobLimit && !loading && (
        <div className="loadMoreRow">
          <button
            className="compactButton"
            onClick={() => setJobLimit((l) => l + PAGE_SIZE)}
            disabled={polling}
          >
            {polling ? 'Loading…' : `Load more (showing ${jobs.length})`}
          </button>
        </div>
      )}
      {toast ? <div className="toastBanner">{toast}</div> : null}
    </main>
  );
}
