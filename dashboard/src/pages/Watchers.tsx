import { FormEvent, useEffect, useState } from 'react';
import { api, type User, type Watcher } from '../api';
import { Topbar } from '../components/Topbar';

type LobCutWindow = Window & {
  watcherAPI?: {
    add: (path: string) => Promise<Watcher>;
    remove: (id: number, path: string) => Promise<{ status: string }>;
    toggle: (id: number, path: string, enabled: boolean) => Promise<Watcher>;
  };
};

type Toast = { tone: 'success' | 'error'; message: string };

type Props = {
  user: User;
};

export function Watchers({ user }: Props) {
  const [watchers, setWatchers] = useState<Watcher[]>([]);
  const [loadingList, setLoadingList] = useState(true);
  const [path, setPath] = useState('');
  const [pipeline, setPipeline] = useState('auto');
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState<Toast | null>(null);

  const showToast = (next: Toast) => {
    setToast(next);
    window.setTimeout(() => setToast(null), 2500);
  };

  const load = async () => {
    try {
      setWatchers(await api.watchers());
    } catch (e) {
      showToast({ tone: 'error', message: e instanceof Error ? e.message : 'Failed to load watchers.' });
    } finally {
      setLoadingList(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!path.trim()) return;
    setSubmitting(true);
    try {
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
      showToast({ tone: 'success', message: 'Watcher started.' });
      await load();
    } catch (e) {
      showToast({ tone: 'error', message: e instanceof Error ? e.message : 'Failed to add watcher.' });
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggle = async (watcher: Watcher, checked: boolean) => {
    try {
      const watcherAPI = (window as LobCutWindow).watcherAPI;
      if (watcherAPI) {
        await watcherAPI.toggle(watcher.id, watcher.path, checked);
      } else {
        await api.updateWatcher(watcher.id, checked);
      }
      await load();
    } catch (e) {
      showToast({ tone: 'error', message: e instanceof Error ? e.message : 'Failed to update watcher.' });
    }
  };

  const handleRemove = async (watcher: Watcher) => {
    try {
      const watcherAPI = (window as LobCutWindow).watcherAPI;
      if (watcherAPI) {
        await watcherAPI.remove(watcher.id, watcher.path);
      } else {
        await api.deleteWatcher(watcher.id);
      }
      await load();
    } catch (e) {
      showToast({ tone: 'error', message: e instanceof Error ? e.message : 'Failed to remove watcher.' });
    }
  };

  return (
    <main className="appShell">
      <Topbar user={user} currentPath="/watchers" />

      <section className="settingsPanel">
        <div className="sectionHead">
          <h1>Watch Folders</h1>
        </div>

        <form className="watcherForm" onSubmit={submit}>
          <input
            value={path}
            onChange={(event) => setPath(event.target.value)}
            placeholder="Enter folder path to monitor..."
            disabled={submitting}
          />
          <select
            value={pipeline}
            onChange={(event) => setPipeline(event.target.value)}
            disabled={submitting}
          >
            <option value="auto">Auto Detect</option>
            <option value="image_pipeline">Images Only</option>
            <option value="video_pipeline">Videos Only</option>
          </select>
          <button type="submit" disabled={submitting || !path.trim()}>
            {submitting ? 'Adding…' : 'Add Watch'}
          </button>
        </form>
      </section>

      <section className="watcherList" style={{ marginTop: 16 }}>
        {loadingList ? (
          <div className="placeholder">Loading watchers…</div>
        ) : watchers.length === 0 ? (
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
                  onChange={(event) => void handleToggle(watcher, event.target.checked)}
                />
                Enabled
              </label>
              <button
                type="button"
                className="compactButton dangerButton"
                onClick={() => void handleRemove(watcher)}
              >
                Remove
              </button>
            </article>
          ))
        )}
      </section>
      {toast ? <div className={`toastBanner ${toast.tone}`}>{toast.message}</div> : null}
    </main>
  );
}
