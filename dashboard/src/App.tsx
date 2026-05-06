import { Login } from './pages/Login';
import { Dashboard } from './pages/Dashboard';
import { Watchers } from './pages/Watchers';
import { Settings } from './pages/Settings';
import { OpenClaw } from './pages/OpenClaw';
import { Profile } from './pages/Profile';
import { useAuth } from './hooks/useAuth';
import { currentPath, navigate } from './navigation';

export function App() {
  const path = currentPath();

  if (path === '/login') {
    return <Login />;
  }

  const { user, loading } = useAuth();
  if (loading) {
    return <div className="boot">LobCut</div>;
  }
  if (!user) {
    navigate('/login');
    return null;
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
