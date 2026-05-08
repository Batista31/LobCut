import { useState } from 'react';
import { api, type User } from '../api';
import { navigate, routeHref } from '../navigation';
import { UserAvatar } from './UserAvatar';

type Props = {
  user: User;
  currentPath: string;
};

export function Topbar({ user, currentPath }: Props) {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <header className="topbar">
      <div className="brandBlock">
        <a href={routeHref('/')} className="brandLink">
          <span className="markFrame">
            <img className="logoImage" src="lobcut-mark.png?v=mark-png" alt="LobCut mark" />
          </span>
          <span className="brandWordmark">LOBCUT</span>
        </a>
      </div>

      <nav>
        <a href={routeHref('/')} className={currentPath === '/' ? 'navActive' : ''}>Jobs</a>
        <a href={routeHref('/watchers')} className={currentPath === '/watchers' ? 'navActive' : ''}>Watchers</a>
        <a href={routeHref('/openclaw')} className={currentPath === '/openclaw' ? 'navActive' : ''}>OpenClaw</a>
        <a href={routeHref('/settings')} className={currentPath === '/settings' ? 'navActive' : ''}>Settings</a>
      </nav>

      <div className="userBlock">
        <div className="avatarWrapper" onClick={() => setMenuOpen((open) => !open)}>
          <UserAvatar user={user} className="avatarImg" fallbackClassName="avatarFallback" />
          {menuOpen && (
            <div className="avatarMenu" onClick={(event) => event.stopPropagation()}>
              <div className="avatarMenuHeader">
                <UserAvatar user={user} className="avatarMenuImg" fallbackClassName="avatarMenuFallback" alt="" />
                <div>
                  <div className="avatarMenuName">{user.name || 'User'}</div>
                  <div className="avatarMenuEmail">{user.email}</div>
                </div>
              </div>
              <div className="avatarMenuDivider" />
              <a href={routeHref('/profile')} className="avatarMenuItem" onClick={() => setMenuOpen(false)}>
                <span>Profile</span>
              </a>
              <a href={routeHref('/settings')} className="avatarMenuItem" onClick={() => setMenuOpen(false)}>
                <span>Settings</span>
              </a>
              <div className="avatarMenuDivider" />
              <a
                href="http://localhost:8000/auth/logout"
                className="avatarMenuItem avatarMenuDanger"
                onClick={async (event) => {
                  event.preventDefault();
                  await api.logout();
                  navigate('/login');
                }}
              >
                <span>Sign out</span>
              </a>
            </div>
          )}
        </div>
      </div>

      {menuOpen && <div className="avatarBackdrop" onClick={() => setMenuOpen(false)} />}
    </header>
  );
}
