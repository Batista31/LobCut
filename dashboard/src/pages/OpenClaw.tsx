import { FormEvent, useEffect, useState } from 'react';
import { api, type OpenClawStatus, type TelegramSettings, type User } from '../api';
import { Topbar } from '../components/Topbar';
import { routeHref } from '../navigation';

type Props = {
  user: User;
};

export function OpenClaw({ user }: Props) {
  const [status, setStatus] = useState<OpenClawStatus | null>(null);
  const [error, setError] = useState('');
  const [telegram, setTelegram] = useState<TelegramSettings | null>(null);
  const [chatId, setChatId] = useState('');
  const [telegramMsg, setTelegramMsg] = useState('');

  const refreshStatus = async () => {
    setError('');
    try {
      setStatus(await api.openClawStatus());
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : 'Could not load OpenClaw status.');
    }
  };

  const loadTelegram = async () => {
    try {
      const settings = await api.telegramSettings();
      setTelegram(settings);
      setChatId(settings.chat_id || '');
    } catch {
      // Telegram settings may not be available
    }
  };

  const saveTelegram = async (event: FormEvent) => {
    event.preventDefault();
    setTelegramMsg('');
    try {
      await api.linkTelegram(chatId.trim());
      await loadTelegram();
      setTelegramMsg('Telegram chat linked successfully.');
    } catch (exc) {
      setTelegramMsg(exc instanceof Error ? exc.message : 'Failed to link Telegram.');
    }
  };

  const testTelegram = async () => {
    setTelegramMsg('');
    try {
      await api.testTelegram();
      setTelegramMsg('Test notification sent!');
    } catch (exc) {
      setTelegramMsg(exc instanceof Error ? exc.message : 'Test failed.');
    }
  };

  useEffect(() => {
    void refreshStatus();
    void loadTelegram();
    const timer = window.setInterval(() => void refreshStatus(), 10000);
    return () => window.clearInterval(timer);
  }, []);

  const gatewayDotClass = !status ? 'yellow'
    : status.gateway.status === 'reachable' ? 'green'
    : status.gateway.status === 'unreachable' ? 'red'
    : 'yellow';

  return (
    <main className="appShell">
      <Topbar user={user} currentPath="/openclaw" />

      <section className="settingsPanel">
        <div className="sectionHead">
          <h1>OpenClaw Dashboard</h1>
          <button type="button" onClick={() => void refreshStatus()}>Refresh</button>
        </div>

        {error ? <p className="errorText" style={{ padding: '0 16px' }}>{error}</p> : null}

        {status ? (
          <div className="openclawGrid">
            <article>
              <span>Gateway</span>
              <strong className="statusIndicator">
                <span className={`statusDot ${gatewayDotClass}`} />
                {status.gateway.status}
              </strong>
              <a href={status.gateway.public_url || status.gateway.url} target="_blank" rel="noreferrer">
                {status.gateway.public_url || status.gateway.url}
              </a>
              {status.gateway.error ? <p className="errorText">{status.gateway.error}</p> : null}
            </article>
            <article>
              <span>Python Service</span>
              <strong className="statusIndicator">
                <span className="statusDot green" />
                configured
              </strong>
              <a href={status.python_service.url} target="_blank" rel="noreferrer">{status.python_service.url}</a>
            </article>
            <article>
              <span>Memory Log</span>
              <strong className="statusIndicator">
                <span className={`statusDot ${status.memory_log_exists ? 'green' : 'yellow'}`} />
                {status.memory_log_exists ? 'available' : 'missing'}
              </strong>
              <code>{status.memory_log_path}</code>
            </article>
            <article>
              <span>Config</span>
              <strong>{String(status.config.name || 'OpenClaw')}</strong>
              <code>{status.config_path}</code>
            </article>

            {/* Telegram integration card */}
            <article className="telegramCard">
              <span>Telegram Notifications</span>
              <strong className="statusIndicator">
                <span className={`statusDot ${telegram?.configured ? (telegram?.linked ? 'green' : 'yellow') : 'red'}`} />
                {!telegram?.configured ? 'bot token not configured' : telegram?.linked ? 'linked' : 'not linked'}
              </strong>
              <form className="settingsForm" onSubmit={saveTelegram}>
                <div className="inlineForm">
                  <input
                    value={chatId}
                    onChange={(e) => setChatId(e.target.value)}
                    placeholder="Telegram Chat ID"
                  />
                  <button type="submit">Link</button>
                  <button
                    type="button"
                    onClick={() => void testTelegram()}
                    disabled={!telegram?.configured || !chatId.trim()}
                  >
                    Test
                  </button>
                </div>
              </form>
              {telegramMsg ? <p className="settingsMessage" style={{ padding: '8px 0 0' }}>{telegramMsg}</p> : null}
              <p className="settingsHint" style={{ padding: '4px 0 0', fontSize: '12px' }}>
                Message your bot first, then paste your numeric chat ID here.
              </p>
            </article>
          </div>
        ) : (
          <p className="settingsHint">Loading OpenClaw status...</p>
        )}
      </section>
    </main>
  );
}
