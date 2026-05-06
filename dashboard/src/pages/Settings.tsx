import { FormEvent, useEffect, useState } from 'react';
import { api, type User } from '../api';
import { Topbar } from '../components/Topbar';

type Props = {
  user: User;
};

type Toast = {
  tone: 'success' | 'error';
  message: string;
};

export function Settings({ user }: Props) {
  const [chatId, setChatId] = useState('');
  const [toast, setToast] = useState<Toast | null>(null);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);

  const showToast = (nextToast: Toast) => {
    setToast(nextToast);
    window.setTimeout(() => setToast(null), 2500);
  };

  useEffect(() => {
    api.settings()
      .then((settings) => setChatId(settings.telegram_chat_id || ''))
      .catch(() => setChatId(''));
  }, []);

  const saveTelegram = async (event: FormEvent) => {
    event.preventDefault();
    const value = chatId.trim();
    if (!/^-?\d+$/.test(value)) {
      showToast({ tone: 'error', message: 'Failed: enter the numeric Telegram Chat ID, not a phone number.' });
      return;
    }
    setSaving(true);
    try {
      await api.saveSetting('telegram_chat_id', value);
      showToast({ tone: 'success', message: 'Saved' });
    } catch (error) {
      showToast({ tone: 'error', message: error instanceof Error ? `Failed: ${error.message}` : 'Failed to save' });
    } finally {
      setSaving(false);
    }
  };

  const testTelegram = async () => {
    setTesting(true);
    try {
      const result = await api.testTelegramNotification();
      if (result.success) {
        showToast({ tone: 'success', message: 'Test message sent!' });
      } else {
        showToast({ tone: 'error', message: `Failed: ${result.error || 'Unknown error'}` });
      }
    } catch (error) {
      showToast({ tone: 'error', message: error instanceof Error ? `Failed: ${error.message}` : 'Failed to send test' });
    } finally {
      setTesting(false);
    }
  };

  return (
    <main className="appShell">
      <Topbar user={user} currentPath="/settings" />

      <section className="settingsPanel telegramSettingsPanel">
        <div className="sectionHead">
          <h1>Telegram Notifications</h1>
        </div>
        <form className="settingsForm telegramSettingsForm" onSubmit={saveTelegram}>
          <label>
            Numeric Telegram Chat ID
            <div className="telegramInputRow">
              <input value={chatId} onChange={(event) => setChatId(event.target.value)} placeholder="123456789" />
              <button type="submit" disabled={saving}>{saving ? 'Saving...' : 'Save'}</button>
              <button type="button" onClick={() => void testTelegram()} disabled={testing}>
                {testing ? 'Sending...' : 'Send Test'}
              </button>
            </div>
          </label>
        </form>
        <div className="settingsHelp telegramHelpGrid">
          <img className="telegramQr" src="lobcut-telegram.png" alt="LobCut Telegram bot QR code" />
          <div>
            <strong>How to find your Chat ID:</strong>
            <ol>
              <li>Scan this QR or open Telegram and search for your LobCut bot.</li>
              <li>Open the chat and send /start.</li>
              <li>Search for @userinfobot, open it, and send /start.</li>
              <li>Copy only the numeric ID it replies with, like 1179051234.</li>
              <li>Paste that number above, click Save, then Send Test.</li>
            </ol>
            <p>
              This is not your phone number. Telegram requires you to start the LobCut bot once before it can send
              private notifications.
            </p>
          </div>
        </div>
      </section>

      {toast ? <div className={`toastBanner ${toast.tone}`}>{toast.message}</div> : null}
    </main>
  );
}
