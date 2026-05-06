import { FormEvent, useEffect, useState } from 'react';
import { api, type TelegramSettings, type User } from '../api';
import { Topbar } from '../components/Topbar';
import { routeHref } from '../navigation';

type Props = {
  user: User;
};

type CaptionConfig = {
  font_size: number;
  color: string;
  highlight_color: string;
  position: string;
  style: string;
};

const DEFAULT_CAPTIONS: CaptionConfig = {
  font_size: 18,
  color: '#ffffff',
  highlight_color: '#ffff00',
  position: 'bottom',
  style: 'highlight',
};

function assColorToHex(assColor: string): string {
  // ASS colors are like &H00FFFFFF (AABBGGRR). Convert to #RRGGBB.
  const match = assColor.match(/&H[0-9a-fA-F]{2}([0-9a-fA-F]{6})/);
  if (!match) return assColor.startsWith('#') ? assColor : '#ffffff';
  const bgr = match[1];
  return `#${bgr.slice(4, 6)}${bgr.slice(2, 4)}${bgr.slice(0, 2)}`;
}

function hexToAssColor(hex: string): string {
  const h = hex.replace('#', '');
  if (h.length !== 6) return `&H00${h.toUpperCase()}`;
  return `&H00${h.slice(4, 6)}${h.slice(2, 4)}${h.slice(0, 2)}`.toUpperCase();
}

export function Settings({ user }: Props) {
  const [telegram, setTelegram] = useState<TelegramSettings | null>(null);
  const [chatId, setChatId] = useState('');
  const [message, setMessage] = useState('');

  // Caption settings state
  const [captions, setCaptions] = useState<CaptionConfig>(DEFAULT_CAPTIONS);
  const [captionMsg, setCaptionMsg] = useState('');
  const [captionLoading, setCaptionLoading] = useState(true);

  const loadTelegram = async () => {
    const settings = await api.telegramSettings();
    setTelegram(settings);
    setChatId(settings.chat_id || '');
  };

  const loadCaptions = async () => {
    try {
      const data = await api.captionSettings();
      setCaptions({
        font_size: data.font_size ?? DEFAULT_CAPTIONS.font_size,
        color: assColorToHex(data.color ?? '&H00FFFFFF'),
        highlight_color: assColorToHex(data.highlight_color ?? '&H0000FFFF'),
        position: data.position ?? DEFAULT_CAPTIONS.position,
        style: data.style ?? DEFAULT_CAPTIONS.style,
      });
    } catch {
      // Use defaults
    } finally {
      setCaptionLoading(false);
    }
  };

  useEffect(() => {
    void loadTelegram();
    void loadCaptions();
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

  const saveCaptions = async (event: FormEvent) => {
    event.preventDefault();
    setCaptionMsg('');
    try {
      await api.updateCaptionSettings({
        font_size: captions.font_size,
        color: hexToAssColor(captions.color),
        highlight_color: hexToAssColor(captions.highlight_color),
        position: captions.position,
        style: captions.style,
      });
      setCaptionMsg('Caption settings saved.');
      window.setTimeout(() => setCaptionMsg(''), 3000);
    } catch (exc) {
      setCaptionMsg(exc instanceof Error ? exc.message : 'Failed to save.');
    }
  };

  return (
    <main className="appShell">
      <Topbar user={user} currentPath="/settings" />

      {/* Telegram Section */}
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

      {/* Caption Settings Section */}
      <section className="settingsPanel captionSection">
        <div className="sectionHead">
          <h1>Caption / Subtitle Settings</h1>
        </div>
        {captionLoading ? (
          <p className="settingsHint">Loading caption settings...</p>
        ) : (
          <form onSubmit={saveCaptions}>
            <div className="captionGrid">
              <label>
                Font Size: {captions.font_size}px
                <input
                  type="range"
                  min={12}
                  max={48}
                  value={captions.font_size}
                  onChange={(e) => setCaptions({ ...captions, font_size: Number(e.target.value) })}
                />
              </label>
              <label>
                Position
                <select
                  value={captions.position}
                  onChange={(e) => setCaptions({ ...captions, position: e.target.value })}
                >
                  <option value="bottom">Bottom</option>
                  <option value="center">Center</option>
                  <option value="top">Top</option>
                </select>
              </label>
              <label>
                Primary Color
                <input
                  type="color"
                  value={captions.color}
                  onChange={(e) => setCaptions({ ...captions, color: e.target.value })}
                />
              </label>
              <label>
                Highlight Color
                <input
                  type="color"
                  value={captions.highlight_color}
                  onChange={(e) => setCaptions({ ...captions, highlight_color: e.target.value })}
                />
              </label>
              <label>
                Style
                <select
                  value={captions.style}
                  onChange={(e) => setCaptions({ ...captions, style: e.target.value })}
                >
                  <option value="highlight">Highlight (active word colored)</option>
                  <option value="word_by_word">Word-by-Word</option>
                  <option value="block">Block (full line)</option>
                </select>
              </label>
            </div>
            <div className="captionPreview">
              <div className="captionPreviewSwatch" style={{ backgroundColor: captions.color }} />
              <div className="captionPreviewSwatch" style={{ backgroundColor: captions.highlight_color }} />
              <span className="captionPreviewText">
                Preview: <span style={{ color: captions.color }}>{captions.font_size}px</span>{' '}
                / <span style={{ color: captions.highlight_color }}>highlighted</span>
              </span>
            </div>
            <div className="settingsActions" style={{ padding: '16px' }}>
              <button type="submit">Save Caption Settings</button>
            </div>
            {captionMsg ? <p className="settingsMessage">{captionMsg}</p> : null}
          </form>
        )}
        <p className="settingsHint">
          These settings control how subtitles are rendered on generated reels and clips.
        </p>
      </section>
    </main>
  );
}
