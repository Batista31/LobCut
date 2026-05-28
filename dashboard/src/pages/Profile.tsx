import { useEffect, useState } from 'react';
import { api, type UsageInfo, type User } from '../api';
import { navigate, routeHref } from '../navigation';
import { Topbar } from '../components/Topbar';
import { setStoredAvatar, UserAvatar } from '../components/UserAvatar';

type Props = { user: User };

export function Profile({ user }: Props) {
  const [avatarSaved, setAvatarSaved] = useState(false);
  const [usage, setUsage] = useState<UsageInfo | null>(null);
  const [upgrading, setUpgrading] = useState(false);
  const [upgradeMsg, setUpgradeMsg] = useState('');

  useEffect(() => {
    api.usage().then(setUsage).catch(() => {});
  }, []);

  const logout = async () => {
    await api.logout();
    navigate('/login');
  };

  const handleAvatarChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) {
      alert('Avatar must be under 2MB');
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      setStoredAvatar(String(reader.result || ''));
      setAvatarSaved(true);
      setTimeout(() => setAvatarSaved(false), 3000);
    };
    reader.readAsDataURL(file);
  };

  const handleUpgrade = async () => {
    setUpgrading(true);
    try {
      await api.upgrade();
      const fresh = await api.usage();
      setUsage(fresh);
      setUpgradeMsg('Upgraded to Pro!');
    } catch (e) {
      setUpgradeMsg(e instanceof Error ? e.message : 'Upgrade failed');
    } finally {
      setUpgrading(false);
    }
  };

  const isFree = !usage || usage.tier === 'free';
  const usedPct = usage?.jobs_limit
    ? Math.min(100, Math.round((usage.jobs_this_week / usage.jobs_limit) * 100))
    : 0;

  return (
    <main className="appShell">
      <Topbar user={user} currentPath="/profile" />

      <div className="profileShell">
        {/* ── Avatar & name ── */}
        <div className="profileCard profileHeroCard">
          <div className="profileAvatarSection">
            <div className="profileAvatarWrap">
              <UserAvatar user={user} className="profileAvatar" fallbackClassName="profileAvatarFallback" />
              <label className="profileAvatarEdit" title="Change avatar">
                <input type="file" accept="image/*" style={{ display: 'none' }} onChange={handleAvatarChange} />
                ✏
              </label>
            </div>
            <div className="profileAvatarInfo">
              <h1 className="profileName">{user.name || 'User'}</h1>
              <p className="profileEmail">{user.email}</p>
              <div className="profileBadgeRow">
                <span className={`tierBadge tierBadge-${usage?.tier ?? 'free'}`}>
                  {usage?.tier === 'pro' ? '★ Pro' : 'Free'}
                </span>
                {avatarSaved && <span className="profileSavedMsg">Avatar updated</span>}
              </div>
            </div>
          </div>
          <button className="profileSignOutBtnInline" type="button" onClick={logout}>Sign out</button>
        </div>

        {/* ── Usage ── */}
        <div className="profileCard">
          <div className="profileCardHeader">
            <h2>Usage this week</h2>
            {usage && <span className="profileCardHint">{usage.jobs_remaining !== null ? `${usage.jobs_remaining} remaining` : 'Unlimited'}</span>}
          </div>

          {!usage && <div className="profileLoadingRow">Loading usage…</div>}

          {usage && (
            <div className="usageBlock">
              <div className="usageBarWrap">
                <div
                  className="usageBarFill"
                  style={{
                    width: `${isFree ? usedPct : 100}%`,
                    background: isFree && usedPct >= 90 ? 'var(--error)' : isFree && usedPct >= 70 ? 'var(--warning)' : 'var(--success)',
                  }}
                />
              </div>
              <div className="usageMeta">
                <span>{usage.jobs_this_week} job{usage.jobs_this_week !== 1 ? 's' : ''} processed</span>
                <span>{usage.jobs_limit !== null ? `/ ${usage.jobs_limit} per week` : '— unlimited'}</span>
              </div>
              <div className="usageDetail">
                Max upload size: <strong>{usage.max_upload_mb}MB</strong>
              </div>

              {isFree && (
                <div className="upgradeCtaBox">
                  <div className="upgradeCtaText">
                    <div className="upgradeCtaTitle">Upgrade to Pro</div>
                    <div className="upgradeCtaDesc">Unlimited jobs, 2GB uploads, priority processing.</div>
                  </div>
                  {upgradeMsg ? (
                    <span className="profileSavedMsg">{upgradeMsg}</span>
                  ) : (
                    <button
                      className="upgradeCtaBtn"
                      onClick={() => void handleUpgrade()}
                      disabled={upgrading}
                    >
                      {upgrading ? 'Upgrading…' : 'Upgrade'}
                    </button>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* ── Quick links ── */}
        <div className="profileCard">
          <div className="profileCardHeader"><h2>Quick Links</h2></div>
          <div className="profileLinks">
            <a href={routeHref('/settings')} className="profileLinkItem">
              <span className="profileLinkIcon">⚙️</span>
              <div><div className="profileLinkTitle">Settings</div><div className="profileLinkDesc">Telegram, captions, output folder</div></div>
              <span className="profileLinkArrow">›</span>
            </a>
            <a href={routeHref('/watchers')} className="profileLinkItem">
              <span className="profileLinkIcon">📁</span>
              <div><div className="profileLinkTitle">Watch Folders</div><div className="profileLinkDesc">Manage monitored directories</div></div>
              <span className="profileLinkArrow">›</span>
            </a>
            <a href={routeHref('/openclaw')} className="profileLinkItem">
              <span className="profileLinkIcon">🦞</span>
              <div><div className="profileLinkTitle">Integrations</div><div className="profileLinkDesc">Telegram notifications</div></div>
              <span className="profileLinkArrow">›</span>
            </a>
          </div>
        </div>

        {/* ── Account details ── */}
        <div className="profileCard">
          <div className="profileCardHeader">
            <h2>Account Details</h2>
            <span className="profileCardHint">Synced from Google</span>
          </div>
          <div className="profileDetail">
            <div className="profileDetailRow"><span>Email</span><span>{user.email || '—'}</span></div>
            <div className="profileDetailRow"><span>Account ID</span><code className="profileDetailCode">{user.sub}</code></div>
          </div>
        </div>
      </div>
    </main>
  );
}
