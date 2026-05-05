import { FormEvent, useEffect, useState } from 'react';
import { api, type User, type Watcher } from '../api';
import { routeHref } from '../navigation';

type Props = {
  user: User;
};

export function Watchers({ user }: Props) {
  const [watchers, setWatchers] = useState<Watcher[]>([]);
  const [path, setPath] = useState('');
  const [pipeline, setPipeline] = useState('auto');

  const load = async () => setWatchers(await api.watchers());

  useEffect(() => {
    void load();
  }, []);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!path.trim()) return;
    await api.addWatcher({
      path: path.trim(),
      pipeline_override: pipeline === 'auto' ? undefined : pipeline,
    });
    setPath('');
    setPipeline('auto');
    await load();
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
        <div className="userBlock"><span>{user.name || user.email}</span></div>
      </header>

      <section className="sectionHead">
        <h1>Watch Folders</h1>
      </section>

      <form className="watcherForm" onSubmit={submit}>
        <input value={path} onChange={(event) => setPath(event.target.value)} placeholder={'D:\\Media\\Inbox'} />
        <select value={pipeline} onChange={(event) => setPipeline(event.target.value)}>
          <option value="auto">auto</option>
          <option value="image_pipeline">image</option>
          <option value="video_pipeline">video</option>
        </select>
        <button type="submit">Add</button>
      </form>

      <section className="watcherList">
        {watchers.map((watcher) => (
          <article className="watcherRow" key={watcher.id}>
            <div>
              <code>{watcher.path}</code>
              <span>{watcher.pipeline_override || 'auto'}</span>
            </div>
            <label className="toggle">
              <input
                type="checkbox"
                checked={watcher.enabled}
                onChange={async (event) => {
                  await api.updateWatcher(watcher.id, event.target.checked);
                  await load();
                }}
              />
              Enabled
            </label>
            <button
              type="button"
              className="dangerButton"
              onClick={async () => {
                await api.deleteWatcher(watcher.id);
                await load();
              }}
            >
              Delete
            </button>
          </article>
        ))}
      </section>
    </main>
  );
}
