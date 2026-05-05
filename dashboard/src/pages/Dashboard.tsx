import { useState } from 'react';
import { api, type Job, type User } from '../api';
import { JobDetail } from '../components/JobDetail';
import { JobsTable } from '../components/JobsTable';
import { StatsBar } from '../components/StatsBar';
import { useJobs } from '../hooks/useJobs';
import { navigate, routeHref } from '../navigation';

type Props = {
  user: User;
};

export function Dashboard({ user }: Props) {
  const [selected, setSelected] = useState<Job | null>(null);
  const { jobs, loading, polling, refresh } = useJobs();

  const logout = async () => {
    await api.logout();
    navigate('/login');
  };

  return (
    <main className="appShell">
      <header className="topbar">
        <a className="wordmark" href={routeHref('/')}>LobCut</a>
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
        onSelect={setSelected}
        selectedId={selected?.id ?? null}
      />
      <JobDetail job={selected} onClose={() => setSelected(null)} />
    </main>
  );
}
