import { FormEvent, useEffect, useState } from 'react';
import { api, type TelegramSettings, type User } from '../api';
import { routeHref } from '../navigation';

type Props = {
  user: User;
};

export function Settings({ user }: Props) {
  const [telegram, setTelegram] = useState<TelegramSettings | null>(null);
  const [chatId, setChatId] = useState('');
  const [message, setMessage] = useState('');

  const loadTelegram = async () => {
    const settings = await api.telegramSettings();
    setTelegram(settings);
    setChatId(settings.chat_id || '');
  };

  useEffect(() => {
    void loadTelegram();
  }, []);

  const saveTelegram = async (event: FormEvent) => {
    event.preventDefault();
    setMessage('');
    await api.linkTelegram(chatId.trim());
    await loadTelegram();
    setMessage('Telegram chat linked.');
  };

  const testTelegram = async () => {
    setMessage('');
    await api.testTelegram();
    setMessage('Test notification sent.');
  };

  return (
    <main className="appShell">
      <header className="topbar">
        <a className="wordmark" href={routeHref('/')}>LobCut</a>
        <nav>
          <a href={routeHref('/')}>Jobs</a>
          <a href={routeHref('/watchers')}>Watchers</a>
          <a href={routeHref('/openclaw')}>OpenClaw</a>
          <a href={routeHref('/settings')}>Settings</a>
        </nav>
        <div className="userBlock"><span>{user.name || user.email}</span></div>
      </header>
      <section className="settingsPanel">
        <div className="sectionHead">
          <h1>Telegram Notifications</h1>
          <span className={telegram?.configured ? 'settingsOk' : 'settingsBad'}>
            {telegram?.configured ? 'bot token configured' : 'bot token missing'}
          </span>
        </div>
        <form className="settingsForm" onSubmit={saveTelegram}>
          <label>
            Chat ID
            <input value={chatId} onChange={(event) => setChatId(event.target.value)} placeholder="123456789" />
          </label>
          <div className="settingsActions">
            <button type="submit">Save</button>
            <button type="button" onClick={() => void testTelegram()} disabled={!telegram?.configured || !chatId.trim()}>
              Send Test
            </button>
          </div>
        </form>
        {message ? <p className="settingsMessage">{message}</p> : null}
        <p className="settingsHint">
          Message your bot first, then paste your numeric Telegram chat ID here. Completed jobs will notify this chat.
        </p>
      </section>
    </main>
  );
}
