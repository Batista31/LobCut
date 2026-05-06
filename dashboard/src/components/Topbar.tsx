import { useState } from 'react';
import { type User } from '../api';
import { routeHref } from '../navigation';

type Props = {
  user: User;
  currentPath: string;
};

export function Topbar({ user, currentPath }: Props) {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <header className="topbar">
      {/* Brand — logo image only, no duplicate text */}
      <div className="brandBlock">
        <a href={routeHref('/')} className="logoLink">
          <img className="logoImage" src="/logo-white.jpeg" alt="LobCut" />
        </a>
      </div>

      {/* Navigation */}
      <nav>
        <a href={routeHref('/')} className={currentPath === '/' ? 'navActive' : ''}>
          Jobs
        </a>
        <a href={routeHref('/watchers')} className={currentPath === '/watchers' ? 'navActive' : ''}>
          Watchers
        </a>
        <a href={routeHref('/openclaw')} className={currentPath === '/openclaw' ? 'navActive' : ''}>
          OpenClaw
        </a>
        <a href={routeHref('/settings')} className={currentPath === '/settings' ? 'navActive' : ''}>
          Settings
        </a>
      </nav>

      {/* Avatar — icon only, clickable → profile */}
      <div className="userBlock">
        <div className="avatarWrapper" onClick={() => setMenuOpen((o) => !o)}>
          {user.picture ? (
            <img className="avatarImg" src={user.picture} alt={user.name || 'Profile'} />
          ) : (
            <span className="avatarFallback">{(user.name || user.email || 'U')[0].toUpperCase()}</span>
          )}
          {menuOpen && (
            <div className="avatarMenu" onClick={(e) => e.stopPropagation()}>
              <div className="avatarMenuHeader">
                {user.picture ? (
                  <img className="avatarMenuImg" src={user.picture} alt="" />
                ) : (
                  <span className="avatarMenuFallback">{(user.name || user.email || 'U')[0].toUpperCase()}</span>
                )}
                <div>
                  <div className="avatarMenuName">{user.name || 'User'}</div>
                  <div className="avatarMenuEmail">{user.email}</div>
                </div>
              </div>
              <div className="avatarMenuDivider" />
              <a href={routeHref('/profile')} className="avatarMenuItem" onClick={() => setMenuOpen(false)}>
                <span>👤</span> Edit Profile
              </a>
              <a href={routeHref('/settings')} className="avatarMenuItem" onClick={() => setMenuOpen(false)}>
                <span>⚙️</span> Settings
              </a>
              <div className="avatarMenuDivider" />
              <a href="http://localhost:8000/auth/logout" className="avatarMenuItem avatarMenuDanger"
                 onClick={async (e) => {
                   e.preventDefault();
                   const { api } = await import('../api');
                   const { navigate } = await import('../navigation');
                   await api.logout();
                   navigate('/login');
                 }}>
                <span>🚪</span> Sign out
              </a>
            </div>
          )}
        </div>
      </div>

      {/* Click-away backdrop */}
      {menuOpen && <div className="avatarBackdrop" onClick={() => setMenuOpen(false)} />}
    </header>
  );
}
