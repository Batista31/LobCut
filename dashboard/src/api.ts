const BASE = (import.meta as { env?: { VITE_API_BASE?: string } }).env?.VITE_API_BASE ?? 'http://localhost:8000';

export type User = {
  sub: string;
  email?: string | null;
  name?: string | null;
  picture?: string | null;
};

export type Job = {
  id: number;
  user_id: string;
  filename: string;
  source_path: string;
  detected_type?: string | null;
  pipeline?: string | null;
  status: string;
  error_message?: string | null;
  ai_category?: string | null;
  ai_tags?: string | null;
  ai_summary?: string | null;
  blur_score?: number | null;
  output_path?: string | null;
  srt_path?: string | null;
  transcript?: string | null;
  game_genre?: string | null;
  game_title?: string | null;
  video_duration?: number | null;
  clip_paths?: string | null;
  reel_path?: string | null;
  highlight_timestamps?: string | null;
  image_url?: string | null;
  created_at: string;
  updated_at: string;
};

export type Watcher = {
  id: number;
  user_id: string;
  path: string;
  media_type?: string | null;
  pipeline_override?: string | null;
  enabled: boolean;
  created_at: string;
  updated_at: string;
};

export type TelegramSettings = {
  configured: boolean;
  linked: boolean;
  chat_id?: string | null;
};

export type OpenClawStatus = {
  gateway: {
    url: string;
    public_url?: string;
    status: string;
    error?: string;
  };
  python_service: {
    url: string;
  };
  config_path: string;
  memory_log_path: string;
  memory_log_exists: boolean;
  config: Record<string, unknown>;
};

export type UsageInfo = {
  tier: 'free' | 'pro';
  jobs_this_week: number;
  jobs_limit: number | null;
  jobs_remaining: number | null;
  max_upload_mb: number;
};

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    credentials: 'include',
  });
  if (res.status === 401) {
    window.location.hash = '#/login';
    throw new Error('Session expired. Please sign in again.');
  }
  if (!res.ok) {
    let message = `Request failed: ${res.status}`;
    try {
      const body = await res.json() as { detail?: string };
      if (body.detail) message = body.detail;
    } catch {
      const text = await res.text().catch(() => '');
      if (text) message = text;
    }
    throw new Error(message);
  }
  return res.json() as Promise<T>;
}

export const api = {
  me: () => apiFetch<User>('/auth/me'),
  usage: () => apiFetch<UsageInfo>('/auth/me/usage'),
  upgrade: () => apiFetch<{ tier: string; status: string }>('/auth/upgrade', { method: 'POST' }),
  jobs: (limit = 50, offset = 0) => apiFetch<Job[]>(`/jobs?limit=${limit}&offset=${offset}`),
  job: (id: number) => apiFetch<Job>(`/jobs/${id}`),
  retryJob: (id: number) => apiFetch<{ status: string }>(`/jobs/retry/${id}`, { method: 'POST' }),
  deleteJob: (id: number) => apiFetch<{ deleted: boolean; job_id: number }>(`/jobs/${id}`, { method: 'DELETE' }),
  watchers: () => apiFetch<Watcher[]>('/watchers'),
  addWatcher: (body: { path: string; pipeline_override?: string }) =>
    apiFetch<Watcher>('/watchers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  updateWatcher: (id: number, enabled: boolean) =>
    apiFetch<Watcher>(`/watchers/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled }),
    }),
  deleteWatcher: (id: number) => apiFetch<{ status: string }>(`/watchers/${id}`, { method: 'DELETE' }),
  settings: () => apiFetch<Record<string, string | null>>('/settings'),
  saveSetting: (key: string, value: string) =>
    apiFetch<{ key: string; value: string }>('/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key, value }),
    }),
  testTelegramNotification: () => apiFetch<{ success: boolean; error?: string }>('/telegram/test', { method: 'POST' }),
  telegramSettings: () => apiFetch<TelegramSettings>('/auth/telegram/settings'),
  linkTelegram: (chat_id: string) =>
    apiFetch<{ status: string }>('/auth/telegram/link', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chat_id }),
    }),
  testTelegram: () => apiFetch<{ status: string }>('/auth/telegram/test', { method: 'POST' }),
  openClawStatus: () => apiFetch<OpenClawStatus>('/openclaw/status'),
  health: () => apiFetch<{ status: string; db: string; version: string }>('/health'),
  logout: () => apiFetch<{ status: string }>('/auth/logout', { method: 'POST' }),
  captionSettings: () => apiFetch<Record<string, unknown>>('/settings/captions'),
  updateCaptionSettings: (body: Record<string, unknown>) =>
    apiFetch<{ status: string }>('/settings/captions', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  updateJobMeta: (id: number, body: { game_genre?: string; game_title?: string; ai_tags?: string }) =>
    apiFetch<Job>(`/jobs/${id}/meta`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  rebuildReel: (
    id: number,
    clipPaths: string[],
    customRanges?: { start: number; end: number }[],
  ) =>
    apiFetch<{ status: string; job_id: number }>(`/jobs/${id}/rebuild-reel`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        clip_paths: clipPaths,
        custom_ranges: customRanges ?? [],
      }),
    }),

  jobVideoUrl: (id: number) => `${BASE}/jobs/${id}/video`,

  // ── Workstation: file upload ──────────────────────────────────
  uploadFile: (file: File, action: string = 'subtitles') => {
    const form = new FormData();
    form.append('file', file);
    form.append('action', action);
    return fetch(`${BASE}/upload`, {
      method: 'POST',
      credentials: 'include',
      body: form,
    }).then(async (res) => {
      if (!res.ok) {
        const body = await res.text();
        throw new Error(body || `Upload failed: ${res.status}`);
      }
      return res.json() as Promise<{ job_id: number; status: string; type: string }>;
    });
  },
};
