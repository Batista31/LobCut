import { navigate } from './navigation';

const BASE = 'http://localhost:8000';

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
  video_duration?: number | null;
  image_url?: string | null;
  created_at: string;
  updated_at: string;
};

export type Watcher = {
  id: number;
  user_id: string;
  path: string;
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

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    credentials: 'include',
  });
  if (res.status === 401) {
    navigate('/login');
    throw new Error('Unauthorized');
  }
  if (!res.ok) {
    const body = await res.text();
    throw new Error(body || `Request failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  me: () => apiFetch<User>('/auth/me'),
  jobs: () => apiFetch<Job[]>('/jobs'),
  job: (id: number) => apiFetch<Job>(`/jobs/${id}`),
  retryJob: (id: number) => apiFetch<{ status: string }>(`/jobs/retry/${id}`, { method: 'POST' }),
  deleteJob: (id: number) => apiFetch<{ status: string }>(`/jobs/${id}`, { method: 'DELETE' }),
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
};
