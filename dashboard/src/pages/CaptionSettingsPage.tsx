import { FormEvent, useEffect, useState } from 'react';
import { api, type User } from '../api';
import { Topbar } from '../components/TopbarLive';

type Props = {
  user: User;
};

type Toast = {
  tone: 'success' | 'error';
  message: string;
};

type CaptionSettings = {
  font: string;
  font_size: number;
  color: string;
  highlight_color: string;
  outline_color: string;
  outline_width: number;
  shadow: number;
  bold: boolean;
  position: 'top' | 'middle' | 'bottom';
  style: 'highlight' | 'word_by_word' | 'block';
  max_words_per_line: number;
};

const defaults: CaptionSettings = {
  font: 'Arial',
  font_size: 18,
  color: '&H00FFFFFF',
  highlight_color: '&H0000FFFF',
  outline_color: '&H00000000',
  outline_width: 3,
  shadow: 1,
  bold: true,
  position: 'bottom',
  style: 'highlight',
  max_words_per_line: 4,
};

const fonts = ['Arial', 'Arial Black', 'Impact', 'Verdana', 'Tahoma', 'Trebuchet MS', 'Georgia'];

function assToHex(value: string) {
  const match = /^&H[0-9A-Fa-f]{2}([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})$/.exec(value);
  if (!match) return '#ffffff';
  const [, blue, green, red] = match;
  return `#${red}${green}${blue}`.toLowerCase();
}

function hexToAss(value: string) {
  const hex = value.replace('#', '');
  if (hex.length !== 6) return '&H00FFFFFF';
  return `&H00${hex.slice(4, 6)}${hex.slice(2, 4)}${hex.slice(0, 2)}`.toUpperCase();
}

function readSettings(raw: Record<string, unknown>): CaptionSettings {
  return {
    ...defaults,
    ...raw,
    font_size: Number(raw.font_size ?? defaults.font_size),
    outline_width: Number(raw.outline_width ?? defaults.outline_width),
    shadow: Number(raw.shadow ?? defaults.shadow),
    max_words_per_line: Number(raw.max_words_per_line ?? defaults.max_words_per_line),
    bold: Boolean(raw.bold ?? defaults.bold),
  } as CaptionSettings;
}

export function CaptionSettingsPage({ user }: Props) {
  const [chatId, setChatId] = useState('');
  const [caption, setCaption] = useState<CaptionSettings>(defaults);
  const [toast, setToast] = useState<Toast | null>(null);
  const [savingTelegram, setSavingTelegram] = useState(false);
  const [savingCaptions, setSavingCaptions] = useState(false);
  const [testing, setTesting] = useState(false);

  const showToast = (nextToast: Toast) => {
    setToast(nextToast);
    window.setTimeout(() => setToast(null), 2500);
  };

  useEffect(() => {
    api.settings()
      .then((settings) => setChatId(settings.telegram_chat_id || ''))
      .catch(() => setChatId(''));
    api.captionSettings()
      .then((settings) => setCaption(readSettings(settings)))
      .catch(() => setCaption(defaults));
  }, []);

  const updateCaption = <K extends keyof CaptionSettings>(key: K, value: CaptionSettings[K]) => {
    setCaption((current) => ({ ...current, [key]: value }));
  };

  const saveTelegram = async (event: FormEvent) => {
    event.preventDefault();
    const value = chatId.trim();
    if (!/^-?\d+$/.test(value)) {
      showToast({ tone: 'error', message: 'Enter the numeric Telegram Chat ID.' });
      return;
    }
    setSavingTelegram(true);
    try {
      await api.saveSetting('telegram_chat_id', value);
      showToast({ tone: 'success', message: 'Telegram settings saved' });
    } catch (error) {
      showToast({ tone: 'error', message: error instanceof Error ? error.message : 'Failed to save Telegram settings' });
    } finally {
      setSavingTelegram(false);
    }
  };

  const saveCaptions = async (event: FormEvent) => {
    event.preventDefault();
    setSavingCaptions(true);
    try {
      await api.updateCaptionSettings(caption);
      showToast({ tone: 'success', message: 'Caption settings saved' });
    } catch (error) {
      showToast({ tone: 'error', message: error instanceof Error ? error.message : 'Failed to save caption settings' });
    } finally {
      setSavingCaptions(false);
    }
  };

  const testTelegram = async () => {
    setTesting(true);
    try {
      const result = await api.testTelegramNotification();
      showToast(result.success
        ? { tone: 'success', message: 'Test message sent' }
        : { tone: 'error', message: result.error || 'Test failed' });
    } catch (error) {
      showToast({ tone: 'error', message: error instanceof Error ? error.message : 'Test failed' });
    } finally {
      setTesting(false);
    }
  };

  const primary = assToHex(caption.color);
  const highlight = assToHex(caption.highlight_color);
  const boundary = assToHex(caption.outline_color);

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
              <button type="submit" disabled={savingTelegram}>{savingTelegram ? 'Saving...' : 'Save'}</button>
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
          </div>
        </div>
      </section>

      <section className="settingsPanel captionSection">
        <div className="sectionHead">
          <h1>Caption / Subtitle Settings</h1>
        </div>
        <form onSubmit={saveCaptions}>
          <div className="captionGrid">
            <label>
              Font
              <select value={caption.font} onChange={(event) => updateCaption('font', event.target.value)}>
                {fonts.map((font) => <option key={font} value={font}>{font}</option>)}
              </select>
            </label>
            <label>
              Font Size: {caption.font_size}px
              <input type="range" min="12" max="72" value={caption.font_size} onChange={(event) => updateCaption('font_size', Number(event.target.value))} />
            </label>
            <label>
              Position
              <select value={caption.position} onChange={(event) => updateCaption('position', event.target.value as CaptionSettings['position'])}>
                <option value="bottom">Bottom</option>
                <option value="middle">Middle</option>
                <option value="top">Top</option>
              </select>
            </label>
            <label>
              Style
              <select value={caption.style} onChange={(event) => updateCaption('style', event.target.value as CaptionSettings['style'])}>
                <option value="highlight">Highlight words</option>
                <option value="word_by_word">Word by word</option>
                <option value="block">Block captions</option>
              </select>
            </label>
            <label>
              Primary Color
              <input type="color" value={primary} onChange={(event) => updateCaption('color', hexToAss(event.target.value))} />
            </label>
            <label>
              Highlight Color
              <input type="color" value={highlight} onChange={(event) => updateCaption('highlight_color', hexToAss(event.target.value))} />
            </label>
            <label>
              Boundary Color
              <input type="color" value={boundary} onChange={(event) => updateCaption('outline_color', hexToAss(event.target.value))} />
            </label>
            <label>
              Boundary: {caption.outline_width}px
              <input type="range" min="0" max="8" value={caption.outline_width} onChange={(event) => updateCaption('outline_width', Number(event.target.value))} />
            </label>
            <label>
              Shadow: {caption.shadow}px
              <input type="range" min="0" max="5" value={caption.shadow} onChange={(event) => updateCaption('shadow', Number(event.target.value))} />
            </label>
            <label>
              Words per line: {caption.max_words_per_line}
              <input type="range" min="1" max="8" value={caption.max_words_per_line} onChange={(event) => updateCaption('max_words_per_line', Number(event.target.value))} />
            </label>
            <label className="captionToggle">
              <input type="checkbox" checked={caption.bold} onChange={(event) => updateCaption('bold', event.target.checked)} />
              Bold letters
            </label>
          </div>
          <div className={`captionPreview captionPreview-${caption.position}`}>
            <span className="captionPreviewSwatch" style={{ backgroundColor: highlight }} />
            <span
              className="captionPreviewText"
              style={{
                color: primary,
                fontFamily: caption.font,
                fontSize: `${caption.font_size}px`,
                fontWeight: caption.bold ? 800 : 500,
                WebkitTextStroke: `${caption.outline_width}px ${boundary}`,
                textShadow: caption.shadow ? `0 ${caption.shadow}px ${caption.shadow * 2}px #000` : 'none',
              }}
            >
              caption preview
            </span>
          </div>
          <div className="settingsActions captionActions">
            <button type="submit" disabled={savingCaptions}>{savingCaptions ? 'Saving...' : 'Save Captions'}</button>
          </div>
        </form>
      </section>

      {toast ? <div className={`toastBanner ${toast.tone}`}>{toast.message}</div> : null}
    </main>
  );
}
