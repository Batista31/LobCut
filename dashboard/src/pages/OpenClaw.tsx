import { FormEvent, useEffect, useState } from 'react';
import { api, type TelegramSettings, type User } from '../api';
import { Topbar } from '../components/Topbar';

type Props = {
  user: User;
};

export function OpenClaw({ user }: Props) {
  const [telegram, setTelegram] = useState<TelegramSettings | null>(null);
  const [chatId, setChatId] = useState('');
  const [telegramMsg, setTelegramMsg] = useState('');

  const loadTelegram = async () => {
    try {
      const settings = await api.telegramSettings();
      setTelegram(settings);
      setChatId(settings.chat_id || '');
    } catch {
      // silently ignore if not configured
    }
  };

  const saveTelegram = async (event: FormEvent) => {
    event.preventDefault();
    setTelegramMsg('');
    if (!/^-?\d+$/.test(chatId.trim())) {
      setTelegramMsg('Enter the numeric Telegram Chat ID, not your phone number.');
      return;
    }
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

  useEffect(() => { void loadTelegram(); }, []);

  return (
    <main className="appShell">
      <Topbar user={user} currentPath="/openclaw" />

      <section className="settingsPanel">
        <div className="sectionHead">
          <h1>Integrations</h1>
        </div>

        <div className="openclawGrid">
          <article className="telegramCard">
            <span>Telegram Notifications</span>
            <strong className="statusIndicator">
              <span className={`statusDot ${telegram?.configured ? (telegram?.linked ? 'green' : 'yellow') : 'red'}`} />
              {!telegram?.configured ? 'bot token not set' : telegram?.linked ? 'linked' : 'not linked'}
            </strong>
            <div className="telegramLinkLayout">
              <div className="telegramQrCard">
                <img className="telegramQr" src="lobcut-telegram.png?v=telegram" alt="LobCut Telegram bot QR code" />
                <span>Scan to open LobCut bot</span>
              </div>
              <div className="telegramLinkContent">
                <form className="settingsForm" onSubmit={saveTelegram}>
                  <div className="inlineForm">
                    <input
                      value={chatId}
                      onChange={(e) => setChatId(e.target.value)}
                      placeholder="Numeric Telegram Chat ID"
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
                <div className="telegramSteps">
                  <strong>How to link:</strong>
                  <ol>
                    <li>Scan the QR code or open the LobCut bot in Telegram.</li>
                    <li>Send /start to the LobCut bot.</li>
                    <li>Open @userinfobot and send /start.</li>
                    <li>Copy the numeric ID it replies with (e.g. 1179051234).</li>
                    <li>Paste it here, click Link, then Test.</li>
                  </ol>
                  <p>This is not your phone number. You must start the bot once before notifications can work.</p>
                </div>
              </div>
            </div>
          </article>
        </div>
      </section>
    </main>
  );
}
