import { useEffect, useState } from 'react';
import { Login } from './pages/Login';
import { Dashboard } from './pages/Dashboard';
import { Watchers } from './pages/Watchers';
import { Settings } from './pages/Settings';
import { OpenClaw } from './pages/OpenClaw';
import { Profile } from './pages/Profile';
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
    return <div className="boot">LobCut</div>;
  }
  if (path === '/login') {
    return <Login />;
  }
  if (!user) {
    return <Login />;
  }
  if (path === '/watchers') {
    return <Watchers user={user} />;
  }
  if (path === '/settings') {
    return <Settings user={user} />;
  }
  if (path === '/openclaw') {
    return <OpenClaw user={user} />;
  }
  if (path === '/profile') {
    return <Profile user={user} />;
  }
  return <Dashboard user={user} />;
}
