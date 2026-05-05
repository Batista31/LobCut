import { useEffect, useState } from 'react';
import { api, type Job, type User } from '../api';
import { JobDetail } from '../components/JobDetail';
import { JobsTable } from '../components/JobsTable';
import { StatsBar } from '../components/StatsBar';
import { useJobs } from '../hooks/useJobs';
import { navigate, routeHref } from '../navigation';

type Props = {
  user: User;
};

const UI_VERSION = 'ui-2026.05.05.2045';

export function Dashboard({ user }: Props) {
  const [selected, setSelected] = useState<Job | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [apiVersion, setApiVersion] = useState<string>('api-checking');
  const { jobs, loading, polling, refresh, setJobs } = useJobs();

  useEffect(() => {
    api.health()
      .then((health) => setApiVersion(`api-${health.version}`))
      .catch(() => setApiVersion('api-unreachable'));
  }, []);

  const showToast = (message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(null), 3000);
  };

  const logout = async () => {
    await api.logout();
    navigate('/login');
  };

  return (
    <main className="appShell">
      <header className="topbar">
        <div className="brandBlock">
          <a className="wordmark" href={routeHref('/')}>LobCut</a>
          <span className="versionTag">{UI_VERSION} / {apiVersion}</span>
        </div>
        <nav>
          <a href={routeHref('/')}>Jobs</a>
          <a href={routeHref('/watchers')}>Watchers</a>
          <a href={routeHref('/openclaw')}>OpenClaw</a>
          <a href={routeHref('/settings')}>Settings</a>
        </nav>
        <div className="userBlock">
          {user.picture ? <img src={user.picture} alt="" /> : <span className="avatarFallback" />}
          <span>{user.name || user.email || 'User'}</span>
          <button type="button" onClick={logout}>Sign out</button>
        </div>
      </header>
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
