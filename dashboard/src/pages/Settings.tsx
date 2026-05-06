import { FormEvent, useEffect, useState } from 'react';
import { api, type TelegramSettings, type User } from '../api';
import { Topbar } from '../components/Topbar';
import { routeHref } from '../navigation';

type Props = {
  user: User;
};

type CaptionConfig = {
  font: string;
  font_size: number;
  color: string;
  highlight_color: string;
  outline_color: string;
  outline_width: number;
  shadow: number;
  bold: boolean;
  position: string;
  style: string;
  max_words_per_line: number;
};

const DEFAULT_CAPTIONS: CaptionConfig = {
  font: 'Arial',
  font_size: 18,
  color: '#ffffff',
  highlight_color: '#ffff00',
  outline_color: '#000000',
  outline_width: 3,
  shadow: 1,
  bold: true,
  position: 'bottom',
  style: 'highlight',
  max_words_per_line: 4,
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

function stringSetting(value: unknown, fallback: string): string {
  return typeof value === 'string' ? value : fallback;
}

function numberSetting(value: unknown, fallback: number): number {
  return typeof value === 'number' ? value : fallback;
}

function boolSetting(value: unknown, fallback: boolean): boolean {
  return typeof value === 'boolean' ? value : fallback;
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
        font: stringSetting(data.font, DEFAULT_CAPTIONS.font),
        font_size: numberSetting(data.font_size, DEFAULT_CAPTIONS.font_size),
        color: assColorToHex(stringSetting(data.color, '&H00FFFFFF')),
        highlight_color: assColorToHex(stringSetting(data.highlight_color, '&H0000FFFF')),
        outline_color: assColorToHex(stringSetting(data.outline_color, '&H00000000')),
        outline_width: numberSetting(data.outline_width, DEFAULT_CAPTIONS.outline_width),
        shadow: numberSetting(data.shadow, DEFAULT_CAPTIONS.shadow),
        bold: boolSetting(data.bold, DEFAULT_CAPTIONS.bold),
        position: stringSetting(data.position, DEFAULT_CAPTIONS.position),
        style: stringSetting(data.style, DEFAULT_CAPTIONS.style),
        max_words_per_line: numberSetting(data.max_words_per_line, DEFAULT_CAPTIONS.max_words_per_line),
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
        font: captions.font,
        font_size: captions.font_size,
        color: hexToAssColor(captions.color),
        highlight_color: hexToAssColor(captions.highlight_color),
        outline_color: hexToAssColor(captions.outline_color),
        outline_width: captions.outline_width,
        shadow: captions.shadow,
        bold: captions.bold,
        position: captions.position,
        style: captions.style,
        max_words_per_line: captions.max_words_per_line,
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
                Font
                <select
                  value={captions.font}
                  onChange={(e) => setCaptions({ ...captions, font: e.target.value })}
                >
                  <option value="Arial">Arial</option>
                  <option value="Arial Black">Arial Black</option>
                  <option value="Impact">Impact</option>
                  <option value="Verdana">Verdana</option>
                  <option value="Tahoma">Tahoma</option>
                  <option value="Trebuchet MS">Trebuchet MS</option>
                  <option value="Georgia">Georgia</option>
                </select>
              </label>
              <label>
                Font Size: {captions.font_size}px
                <input
                  type="range"
                  min={12}
                  max={72}
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
                  <option value="middle">Middle</option>
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
                Boundary Color
                <input
                  type="color"
                  value={captions.outline_color}
                  onChange={(e) => setCaptions({ ...captions, outline_color: e.target.value })}
                />
              </label>
              <label>
                Boundary: {captions.outline_width}px
                <input
                  type="range"
                  min={0}
                  max={8}
                  step={0.5}
                  value={captions.outline_width}
                  onChange={(e) => setCaptions({ ...captions, outline_width: Number(e.target.value) })}
                />
              </label>
              <label>
                Shadow: {captions.shadow}px
                <input
                  type="range"
                  min={0}
                  max={5}
                  step={0.5}
                  value={captions.shadow}
                  onChange={(e) => setCaptions({ ...captions, shadow: Number(e.target.value) })}
                />
              </label>
              <label>
                Words per line: {captions.max_words_per_line}
                <input
                  type="range"
                  min={1}
                  max={8}
                  value={captions.max_words_per_line}
                  onChange={(e) => setCaptions({ ...captions, max_words_per_line: Number(e.target.value) })}
                />
              </label>
              <label className="captionToggle">
                <input
                  type="checkbox"
                  checked={captions.bold}
                  onChange={(e) => setCaptions({ ...captions, bold: e.target.checked })}
                />
                Bold letters
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
            <div className={`captionPreview captionPreview-${captions.position}`}>
              <div
                className="captionPreviewText"
                style={{
                  color: captions.color,
                  fontFamily: captions.font,
                  fontSize: `${Math.max(18, captions.font_size)}px`,
                  fontWeight: captions.bold ? 800 : 600,
                  WebkitTextStroke: `${captions.outline_width}px ${captions.outline_color}`,
                  textShadow: captions.shadow ? `0 ${captions.shadow}px ${captions.shadow * 2}px rgba(0,0,0,0.85)` : 'none',
                }}
              >
                MAKE IT <span style={{ color: captions.highlight_color }}>POP</span>
              </div>
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
