import { useEffect, useState } from 'react';
import { api, type User } from '../api';
import { navigate, routeHref } from '../navigation';
import { UserAvatar } from './UserAvatar';
import { useTheme } from '../hooks/useTheme';

type Props = {
  user: User;
  currentPath: string;
};

export function Topbar({ user, currentPath }: Props) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [navOpen, setNavOpen] = useState(false);
  const { theme, toggleTheme } = useTheme();

  const logoSrc = theme === 'light' ? 'lobcut-mark-light.png' : 'lobcut-mark.png';

  // Close mobile nav on route change
  useEffect(() => { setNavOpen(false); }, [currentPath]);

  // Close mobile nav on outside click
  useEffect(() => {
    if (!navOpen) return;
    const handler = (e: MouseEvent) => {
      const target = e.target as Element;
      if (!target.closest('.topbar')) setNavOpen(false);
    };
    document.addEventListener('click', handler);
    return () => document.removeEventListener('click', handler);
  }, [navOpen]);

  const navLinks = [
    { href: routeHref('/workstation'), path: '/workstation', label: '✦ Workstation', className: 'navWorkstation' },
    { href: routeHref('/'),            path: '/',            label: 'Jobs' },
    { href: routeHref('/watchers'),    path: '/watchers',    label: 'Watchers' },
    { href: routeHref('/settings'),    path: '/settings',    label: 'Settings' },
    { href: routeHref('/openclaw'),    path: '/openclaw',    label: 'Integrations' },
  ];

  return (
    <header className="topbar">
      {/* Brand */}
      <div className="brandBlock">
        <a href={routeHref('/')} className="brandLink">
          <span className="markFrame">
            <img className="logoImage" src={logoSrc} alt="LobCut" />
          </span>
          <span className="brandWordmark">LOBCUT</span>
        </a>
      </div>

      {/* Desktop nav */}
      <nav className="topbarNav">
        {navLinks.map(({ href, path, label, className }) => (
          <a
            key={path}
            href={href}
            className={[
              className ?? '',
              currentPath === path || (path !== '/' && currentPath.startsWith(path)) ? 'navActive' : '',
            ].filter(Boolean).join(' ') || undefined}
          >
            {label}
          </a>
        ))}
      </nav>

      {/* Right side */}
      <div className="userBlock">
        <button
          className="themeToggle"
          onClick={toggleTheme}
          title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          aria-label="Toggle theme"
        >
          {theme === 'dark' ? '☀' : '◐'}
        </button>

        {/* Mobile hamburger */}
        <button
          className={`hamburger ${navOpen ? 'open' : ''}`}
          onClick={() => setNavOpen((o) => !o)}
          aria-label="Toggle navigation"
        >
          <span /><span /><span />
        </button>

        {/* Avatar menu */}
        <div className="avatarWrapper" onClick={() => setMenuOpen((o) => !o)}>
          <UserAvatar user={user} className="avatarImg" fallbackClassName="avatarFallback" />

          {menuOpen && (
            <div className="avatarMenu" onClick={(e) => e.stopPropagation()}>
              <div className="avatarMenuHeader">
                <UserAvatar user={user} className="avatarMenuImg" fallbackClassName="avatarMenuFallback" alt="" />
                <div>
                  <div className="avatarMenuName">{user.name || 'User'}</div>
                  <div className="avatarMenuEmail">{user.email}</div>
                </div>
              </div>
              <div className="avatarMenuDivider" />
              <a href={routeHref('/profile')}  className="avatarMenuItem" onClick={() => setMenuOpen(false)}>Profile</a>
              <a href={routeHref('/settings')} className="avatarMenuItem" onClick={() => setMenuOpen(false)}>Settings</a>
              <div className="avatarMenuDivider" />
              <a
                href="#"
                className="avatarMenuItem avatarMenuDanger"
                onClick={async (e) => {
                  e.preventDefault();
                  setMenuOpen(false);
                  await api.logout();
                  navigate('/login');
                }}
              >
                Sign out
              </a>
            </div>
          )}
        </div>
      </div>

      {menuOpen && <div className="avatarBackdrop" onClick={() => setMenuOpen(false)} />}

      {/* Mobile nav drawer */}
      {navOpen && (
        <nav className="mobileNav">
          {navLinks.map(({ href, path, label, className }) => (
            <a
              key={path}
              href={href}
              className={[
                'mobileNavLink',
                className ?? '',
                currentPath === path || (path !== '/' && currentPath.startsWith(path)) ? 'navActive' : '',
              ].filter(Boolean).join(' ')}
              onClick={() => setNavOpen(false)}
            >
              {label}
            </a>
          ))}
        </nav>
      )}
    </header>
  );
}
