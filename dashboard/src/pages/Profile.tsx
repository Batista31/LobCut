import { useState } from 'react';
import { api, type User } from '../api';
import { navigate, routeHref } from '../navigation';
import { Topbar } from '../components/Topbar';

type Props = {
  user: User;
};

export function Profile({ user }: Props) {
  const [displayName, setDisplayName] = useState(user.name || '');
  const [saved, setSaved] = useState(false);

  const logout = async () => {
    await api.logout();
    navigate('/login');
  };

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    // Name edits are Google-account driven — show a note
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  return (
    <main className="appShell">
      <Topbar user={user} currentPath="/profile" />

      <div className="profileShell">
        {/* Avatar section */}
        <div className="profileCard">
          <div className="profileAvatarSection">
            {user.picture ? (
              <img className="profileAvatar" src={user.picture} alt={user.name || 'Profile'} />
            ) : (
              <span className="profileAvatarFallback">
                {(user.name || user.email || 'U')[0].toUpperCase()}
              </span>
            )}
            <div className="profileAvatarInfo">
              <h1 className="profileName">{user.name || 'User'}</h1>
              <p className="profileEmail">{user.email}</p>
              <span className="profileBadge">Google Account</span>
            </div>
          </div>
        </div>

        {/* Account details */}
        <div className="profileCard">
          <div className="profileCardHeader">
            <h2>Account Details</h2>
            <span className="profileCardHint">Synced from Google</span>
          </div>
          <form className="profileForm" onSubmit={handleSave}>
            <label>
              Display Name
              <input
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="Your name"
              />
            </label>
            <label>
              Email Address
              <input value={user.email || ''} disabled className="profileInputDisabled" />
            </label>
            <label>
              Account ID
              <input value={user.sub} disabled className="profileInputDisabled" />
            </label>
            <div className="profileActions">
              <button type="submit">Save Changes</button>
              {saved && <span className="profileSavedMsg">✓ Changes noted — name is managed by Google</span>}
            </div>
          </form>
        </div>

        {/* Quick links */}
        <div className="profileCard">
          <div className="profileCardHeader">
            <h2>Quick Links</h2>
          </div>
          <div className="profileLinks">
            <a href={routeHref('/settings')} className="profileLinkItem">
              <span className="profileLinkIcon">⚙️</span>
              <div>
                <div className="profileLinkTitle">Settings</div>
                <div className="profileLinkDesc">Telegram, captions, and pipeline options</div>
              </div>
              <span className="profileLinkArrow">›</span>
            </a>
            <a href={routeHref('/watchers')} className="profileLinkItem">
              <span className="profileLinkIcon">📁</span>
              <div>
                <div className="profileLinkTitle">Watch Folders</div>
                <div className="profileLinkDesc">Manage folders LobCut monitors</div>
              </div>
              <span className="profileLinkArrow">›</span>
            </a>
            <a href={routeHref('/openclaw')} className="profileLinkItem">
              <span className="profileLinkIcon">🦞</span>
              <div>
                <div className="profileLinkTitle">OpenClaw</div>
                <div className="profileLinkDesc">AI agent gateway and Telegram status</div>
              </div>
              <span className="profileLinkArrow">›</span>
            </a>
          </div>
        </div>

        {/* Danger zone */}
        <div className="profileCard profileDangerCard">
          <div className="profileCardHeader">
            <h2>Session</h2>
          </div>
          <div className="profileDangerBody">
            <div>
              <div className="profileDangerTitle">Sign out of LobCut</div>
              <div className="profileDangerDesc">You'll need to sign in again with your Google account.</div>
            </div>
            <button type="button" className="profileSignOutBtn" onClick={logout}>
              Sign Out
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}
