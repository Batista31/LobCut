import { useEffect, useState } from 'react';
import { api, type OpenClawStatus, type User } from '../api';
import { routeHref } from '../navigation';

type Props = {
  user: User;
};

export function OpenClaw({ user }: Props) {
  const [status, setStatus] = useState<OpenClawStatus | null>(null);
  const [error, setError] = useState('');

  const refresh = async () => {
    setError('');
    try {
      setStatus(await api.openClawStatus());
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : 'Could not load OpenClaw status.');
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

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
        <div className="userBlock"><span>{user.name || user.email}</span></div>
      </header>

      <section className="settingsPanel">
        <div className="sectionHead">
          <h1>OpenClaw Dashboard</h1>
          <button type="button" onClick={() => void refresh()}>Refresh</button>
        </div>

        {error ? <p className="errorText">{error}</p> : null}

        {status ? (
          <div className="openclawGrid">
            <article>
              <span>Gateway</span>
              <strong>{status.gateway.status}</strong>
              <a href={status.gateway.public_url || status.gateway.url} target="_blank" rel="noreferrer">
                {status.gateway.public_url || status.gateway.url}
              </a>
              {status.gateway.error ? <p className="errorText">{status.gateway.error}</p> : null}
            </article>
            <article>
              <span>Python Service</span>
              <strong>configured</strong>
              <a href={status.python_service.url} target="_blank" rel="noreferrer">{status.python_service.url}</a>
            </article>
            <article>
              <span>Memory Log</span>
              <strong>{status.memory_log_exists ? 'available' : 'missing'}</strong>
              <code>{status.memory_log_path}</code>
            </article>
            <article>
              <span>Config</span>
              <strong>{String(status.config.name || 'OpenClaw')}</strong>
              <code>{status.config_path}</code>
            </article>
          </div>
        ) : (
          <p className="settingsHint">Loading OpenClaw status...</p>
        )}
      </section>
    </main>
  );
}
