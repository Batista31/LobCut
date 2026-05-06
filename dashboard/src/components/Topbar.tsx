import { useState } from 'react';
import { api, type User } from '../api';
import { navigate, routeHref } from '../navigation';

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
            <img className="logoImage" src="lobcut-mark.jpeg?v=mark" alt="LobCut mark" />
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
          {user.picture ? (
            <img className="avatarImg" src={user.picture} alt={user.name || 'Profile'} />
          ) : (
            <span className="avatarFallback">{(user.name || user.email || 'U')[0].toUpperCase()}</span>
          )}
          {menuOpen && (
            <div className="avatarMenu" onClick={(event) => event.stopPropagation()}>
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
