import { FormEvent, useEffect, useState } from 'react';
import { api, type User, type Watcher } from '../api';
import { Topbar } from '../components/TopbarLive';

type LobCutWindow = Window & {
  watcherAPI?: {
    add: (path: string) => Promise<Watcher>;
    remove: (id: number, path: string) => Promise<{ status: string }>;
    toggle: (id: number, path: string, enabled: boolean) => Promise<Watcher>;
  };
};

type Props = {
  user: User;
};

export function Watchers({ user }: Props) {
  const [watchers, setWatchers] = useState<Watcher[]>([]);
  const [path, setPath] = useState('');
  const [pipeline, setPipeline] = useState('auto');
  const [message, setMessage] = useState('');

  const load = async () => setWatchers(await api.watchers());

  useEffect(() => {
    void load();
  }, []);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!path.trim()) return;
    const watcherAPI = (window as LobCutWindow).watcherAPI;
    if (watcherAPI) {
      await watcherAPI.add(path.trim());
    } else {
      await api.addWatcher({
        path: path.trim(),
        pipeline_override: pipeline === 'auto' ? undefined : pipeline,
      });
    }
    setPath('');
    setPipeline('auto');
    setMessage('Watcher started.');
    window.setTimeout(() => setMessage(''), 2000);
    await load();
  };

  return (
    <main className="appShell">
      <Topbar user={user} currentPath="/watchers" />

      <section className="settingsPanel">
        <div className="sectionHead">
          <h1>Watch Folders</h1>
        </div>

        <form className="watcherForm" onSubmit={submit}>
          <input value={path} onChange={(event) => setPath(event.target.value)} placeholder="Enter folder path to monitor..." />
          <select value={pipeline} onChange={(event) => setPipeline(event.target.value)}>
            <option value="auto">Auto Detect</option>
            <option value="image_pipeline">Images Only</option>
            <option value="video_pipeline">Videos Only</option>
          </select>
          <button type="submit">Add Watch</button>
        </form>
      </section>

      <section className="watcherList" style={{ marginTop: 16 }}>
        {watchers.length === 0 ? (
          <div className="placeholder">No watch folders configured yet. Add one above to start monitoring.</div>
        ) : (
          watchers.map((watcher) => (
            <article className="watcherRow" key={watcher.id}>
              <div>
                <i className={`watcherDot ${watcher.enabled ? 'active' : ''}`} />
                <code>{watcher.path}</code>
                <span>{watcher.pipeline_override || 'auto'}</span>
              </div>
              <label className="toggle">
                <input
                  type="checkbox"
                  checked={watcher.enabled}
                  onChange={async (event) => {
                    const watcherAPI = (window as LobCutWindow).watcherAPI;
                    if (watcherAPI) {
                      await watcherAPI.toggle(watcher.id, watcher.path, event.target.checked);
                    } else {
                      await api.updateWatcher(watcher.id, event.target.checked);
                    }
                    await load();
                  }}
                />
                Enabled
              </label>
              <button
                type="button"
                className="compactButton dangerButton"
                onClick={async () => {
                  const watcherAPI = (window as LobCutWindow).watcherAPI;
                  if (watcherAPI) {
                    await watcherAPI.remove(watcher.id, watcher.path);
                  } else {
                    await api.deleteWatcher(watcher.id);
                  }
                  await load();
                }}
              >
                Remove
              </button>
            </article>
          ))
        )}
      </section>
      {message ? <div className="toastBanner success">{message}</div> : null}
    </main>
  );
}
