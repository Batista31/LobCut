import { useEffect, useState } from 'react';
import { Login } from './pages/Login';
import { Dashboard } from './pages/Dashboard';
import { Watchers } from './pages/Watchers';
import { Settings } from './pages/Settings';
import { OpenClaw } from './pages/OpenClaw';
import { Profile } from './pages/Profile';
import { Workstation } from './pages/Workstation';
import { ErrorBoundary } from './components/ErrorBoundary';
import { useAuth } from './hooks/useAuth';
import { currentPath } from './navigation';

export function App() {
  const [path, setPath] = useState(currentPath());
  const { user, loading } = useAuth();

  useEffect(() => {
    const updatePath = () => setPath(currentPath());
    window.addEventListener('hashchange', updatePath);
    window.addEventListener('popstate', updatePath);
    return () => {
      window.removeEventListener('hashchange', updatePath);
      window.removeEventListener('popstate', updatePath);
    };
  }, []);

  if (loading) {
    return (
      <div className="boot">
        <div className="bootSpinner" />
        <span>LobCut</span>
      </div>
    );
  }
  if (path === '/login' || !user) {
    return <Login />;
  }

  let page: JSX.Element;
  const jobWsMatch = path.match(/^\/workstation\/job\/(\d+)$/);
  if (path === '/workstation') {
    page = <Workstation user={user} />;
  } else if (jobWsMatch) {
    page = <Workstation user={user} jobId={parseInt(jobWsMatch[1], 10)} />;
  } else if (path === '/watchers') {
    page = <Watchers user={user} />;
  } else if (path === '/settings') {
    page = <Settings user={user} />;
  } else if (path === '/openclaw') {
    page = <OpenClaw user={user} />;
  } else if (path === '/profile') {
    page = <Profile user={user} />;
  } else {
    page = <Dashboard user={user} />;
  }

  return <ErrorBoundary>{page}</ErrorBoundary>;
}
