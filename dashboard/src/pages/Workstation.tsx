import { useCallback, useEffect, useRef, useState } from 'react';
import { api, type Job, type User, type UsageInfo } from '../api';
import { Topbar } from '../components/Topbar';
import { navigate } from '../navigation';

type Props = { user: User; jobId?: number };

type FileKind = 'image' | 'video' | 'unknown';

const IMAGE_EXTS = new Set(['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp', '.heic']);
const VIDEO_EXTS = new Set(['.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.m4v']);

function getKind(file: File): FileKind {
  const ext = '.' + (file.name.split('.').pop() ?? '').toLowerCase();
  if (IMAGE_EXTS.has(ext)) return 'image';
  if (VIDEO_EXTS.has(ext)) return 'video';
  return 'unknown';
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDuration(secs?: number | null): string {
  if (!secs) return '—';
  const total = Math.round(secs);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

function parseTagsDisplay(value?: string | null): string {
  if (!value) return '—';
  try {
    const parsed = JSON.parse(value);
    if (Array.isArray(parsed)) return parsed.join(', ') || '—';
  } catch { /* fallthrough */ }
  return value;
}

type WsState =
  | { phase: 'idle' }
  | { phase: 'ready'; file: File; kind: FileKind }
  | { phase: 'uploading' }
  | { phase: 'processing'; jobId: number; action: string }
  | { phase: 'done'; job: Job }
  | { phase: 'error'; message: string };

const ACTION_META: Record<string, { icon: string; label: string; description: string }> = {
  reel:      { icon: '🎞',  label: 'Highlight Reel',         description: 'Auto-select best clips + burn captions' },
  captions:  { icon: '🔥',  label: 'Burn Captions to Video', description: 'Full video with captions from Settings' },
  subtitles: { icon: '📄',  label: 'Export Subtitle File',   description: 'Transcribe only → .srt file, no burning' },
  classify:  { icon: '🔍',  label: 'Classify Image',         description: 'AI category, tags, blur score' },
};

export function Workstation({ user, jobId }: Props) {
  const [jobWsData, setJobWsData] = useState<Job | null>(null);
  const [jobWsLoading, setJobWsLoading] = useState(false);
  const [jobWsError, setJobWsError] = useState('');
  const [state, setState] = useState<WsState>({ phase: 'idle' });
  const [dragOver, setDragOver] = useState(false);
  const [usage, setUsage] = useState<UsageInfo | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  useEffect(() => {
    api.usage().then(setUsage).catch(() => {});
  }, []);

  useEffect(() => {
    if (!jobId) return;
    setJobWsLoading(true);
    api.job(jobId)
      .then((j) => { setJobWsData(j); setJobWsLoading(false); })
      .catch((e: unknown) => {
        setJobWsError(e instanceof Error ? e.message : 'Could not load job.');
        setJobWsLoading(false);
      });
  }, [jobId]);

  const startPolling = useCallback((jobId: number) => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const job = await api.job(jobId);
        if (job.status === 'DONE') {
          if (pollRef.current) clearInterval(pollRef.current);
          setState({ phase: 'done', job });
        } else if (job.status === 'FAILED') {
          if (pollRef.current) clearInterval(pollRef.current);
          setState({ phase: 'error', message: job.error_message ?? 'Processing failed.' });
        }
      } catch (err) {
        console.error('Poll error', err);
      }
    }, 2500);
  }, []);

  const handleFile = useCallback((file: File) => {
    const kind = getKind(file);
    if (kind === 'unknown') {
      setState({ phase: 'error', message: `Unsupported file type: .${file.name.split('.').pop()}` });
      return;
    }
    const maxMB = usage?.max_upload_mb ?? 2000;
    if (file.size > maxMB * 1024 * 1024) {
      setState({ phase: 'error', message: `File too large (${formatBytes(file.size)}). Maximum allowed: ${maxMB}MB.` });
      return;
    }
    setState({ phase: 'ready', file, kind });
  }, [usage]);

  const handleDrop = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }, [handleFile]);

  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
    e.target.value = '';
  }, [handleFile]);

  const runAction = useCallback(async (action: string) => {
    if (state.phase !== 'ready') return;
    const { file } = state;

    setState({ phase: 'uploading' });
    try {
      const { job_id } = await api.uploadFile(file, action);
      setState({ phase: 'processing', jobId: job_id, action });
      startPolling(job_id);
    } catch (err) {
      setState({ phase: 'error', message: err instanceof Error ? err.message : 'Upload failed.' });
    }
  }, [state, startPolling]);

  const reset = () => {
    if (pollRef.current) clearInterval(pollRef.current);
    setState({ phase: 'idle' });
  };

  if (jobId) {
    return (
      <main className="appShell">
        <Topbar user={user} currentPath="/workstation" />
        {jobWsLoading && <div className="wsProgressCard" style={{ margin: '32px 0' }}><div className="wsProgressHeader"><div className="wsSpinner" /><div className="wsProgressTitle">Loading job…</div></div></div>}
        {jobWsError && <div className="wsResultCard" style={{ margin: '32px 0' }}><div className="wsResultError">{jobWsError}</div><button className="wsNewJobBtn" onClick={() => navigate('/workstation')}>Back</button></div>}
        {jobWsData && <JobWorkstation job={jobWsData} onJobUpdate={setJobWsData} />}
      </main>
    );
  }

  return (
    <main className="appShell">
      <Topbar user={user} currentPath="/workstation" />

      <div className="workstationShell">
        <div className="workstationHeader">
          <h2>Workstation</h2>
          <p>Upload a file and process it directly — no watchers or desktop app needed.</p>
        </div>

        {/* ── Idle / Drop Zone ── */}
        {state.phase === 'idle' && (
          <div
            className={`dropZone${dragOver ? ' dragOver' : ''}`}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
          >
            <input
              type="file"
              accept="image/*,video/*,.webp,.heic,.webm,.mkv"
              onChange={handleInputChange}
            />
            <span className="dropZoneIcon">⬆</span>
            <p className="dropZoneTitle">Drop your file here or click to browse</p>
            <p className="dropZoneHint">Images and videos are processed by the AI pipeline</p>
            <p className="dropZoneFormats">jpg · png · webp · heic · mp4 · mov · mkv · webm · avi</p>
          </div>
        )}

        {/* ── File Ready ── */}
        {state.phase === 'ready' && (
          <>
            <div className="filePreviewCard">
              <span className="filePreviewIcon">{state.kind === 'video' ? '🎬' : '🖼'}</span>
              <div className="filePreviewInfo">
                <div className="filePreviewName">{state.file.name}</div>
                <div className="filePreviewMeta">{state.kind.toUpperCase()} · {formatBytes(state.file.size)}</div>
              </div>
              <button className="filePreviewClear" onClick={reset} title="Remove file">✕</button>
            </div>

            <div className="workstationActions">
              {state.kind === 'image' && (
                <ActionCard
                  action="classify"
                  primary
                  onClick={() => runAction('classify')}
                />
              )}
              {state.kind === 'video' && (
                <>
                  <ActionCard action="reel"      primary onClick={() => runAction('reel')} />
                  <ActionCard action="captions"         onClick={() => runAction('captions')} />
                  <ActionCard action="subtitles"        onClick={() => runAction('subtitles')} />
                </>
              )}
            </div>
          </>
        )}

        {/* ── Uploading ── */}
        {state.phase === 'uploading' && (
          <div className="wsProgressCard">
            <div className="wsProgressHeader">
              <div className="wsSpinner" />
              <div>
                <div className="wsProgressTitle">Uploading…</div>
                <div className="wsProgressSub">Sending file to the server</div>
              </div>
            </div>
            <div className="wsProgressBar"><div className="wsProgressBarFill" /></div>
          </div>
        )}

        {/* ── Processing ── */}
        {state.phase === 'processing' && (
          <div className="wsProgressCard">
            <div className="wsProgressHeader">
              <div className="wsSpinner" />
              <div>
                <div className="wsProgressTitle">
                  {ACTION_META[state.action]?.label ?? 'Processing'}…
                </div>
                <div className="wsProgressSub">Job #{state.jobId} · checking every 2.5s</div>
              </div>
            </div>
            <div className="wsProgressBar"><div className="wsProgressBarFill" /></div>
          </div>
        )}

        {/* ── Error ── */}
        {state.phase === 'error' && (
          <div className="wsResultCard">
            <div className="wsResultHeader">
              <span className="wsResultTitle">❌ Failed</span>
            </div>
            <div className="wsResultError">{state.message}</div>
            <div className="wsResultActions">
              <button className="wsNewJobBtn" onClick={reset}>Try Again</button>
            </div>
          </div>
        )}

        {/* ── Done ── */}
        {state.phase === 'done' && <WorkstationResult job={state.job} onReset={reset} />}
      </div>
    </main>
  );
}

function ActionCard({ action, primary, onClick }: { action: string; primary?: boolean; onClick: () => void }) {
  const meta = ACTION_META[action];
  if (!meta) return null;
  return (
    <button
      className={`wsActionCard${primary ? ' primary' : ''}`}
      onClick={onClick}
    >
      <span className="wsActionIcon">{meta.icon}</span>
      <span className="wsActionTitle">{meta.label}</span>
      <span className="wsActionDesc">{meta.description}</span>
    </button>
  );
}

function WorkstationResult({ job, onReset }: { job: Job; onReset: () => void }) {
  const isImage = job.detected_type?.toUpperCase() === 'IMAGE' || !!(job.image_url);
  const isVideo = job.detected_type?.toUpperCase() === 'VIDEO';
  const baseUrl = (import.meta as { env?: { VITE_API_BASE?: string } }).env?.VITE_API_BASE ?? 'http://localhost:8000';

  return (
    <div className="wsResultCard">
      <div className="wsResultHeader">
        <span className="wsResultTitle">✅ Done — {job.filename}</span>
      </div>
      <div className="wsResultBody">
        {/* Image preview */}
        {isImage && job.image_url && (
          <img
            className="wsResultImage"
            src={`${baseUrl}${job.image_url}`}
            alt={job.filename}
          />
        )}

        {/* Image fields */}
        {isImage && (
          <>
            <Row label="Category" value={job.ai_category ?? '—'} />
            <Row label="Tags"     value={parseTagsDisplay(job.ai_tags)} />
            <Row label="Summary"  value={job.ai_summary ?? '—'} />
            {job.blur_score != null && (
              <Row
                label="Blur score"
                value={`${job.blur_score.toFixed(1)} ${job.blur_score < 100 ? '· blurry' : '· sharp'}`}
              />
            )}
          </>
        )}

        {/* Video fields */}
        {isVideo && (
          <>
            <Row label="Duration" value={formatDuration(job.video_duration)} />
            {job.game_title && (
              <Row label="Game" value={`${job.game_title}${job.game_genre ? ` · ${job.game_genre}` : ''}`} />
            )}
            {job.reel_path && <Row label="Reel file"  value={job.reel_path}  mono />}
            {job.srt_path  && (
              <div className="wsResultRow">
                <span className="wsResultLabel">Subtitles</span>
                <span className="wsResultValue">
                  <span style={{ fontFamily: 'monospace', fontSize: '12px', display: 'block', marginBottom: '6px' }}>
                    {job.srt_path}
                  </span>
                  <a
                    className="wsDownloadLink"
                    href={`${baseUrl}/files/srt/${encodeURIComponent(job.srt_path.split(/[\\/]/).pop() ?? '')}`}
                    download
                  >
                    ⬇ Download .srt
                  </a>
                </span>
              </div>
            )}
            {job.transcript && (
              <div className="wsResultRow">
                <span className="wsResultLabel">Transcript</span>
                <span className="wsResultValue" style={{ whiteSpace: 'pre-wrap', maxHeight: '110px', overflowY: 'auto', display: 'block', fontSize: '12px', color: 'var(--text-secondary)' }}>
                  {job.transcript.slice(0, 600)}{job.transcript.length > 600 ? '…' : ''}
                </span>
              </div>
            )}
          </>
        )}

        {job.output_path && <Row label="Output" value={job.output_path} mono />}
      </div>

      <div className="wsResultActions">
        <button className="wsNewJobBtn btnPrimary" onClick={onReset}>Process Another File</button>
        <button className="wsNewJobBtn" onClick={() => { window.location.hash = '#/'; }}>View in Jobs</button>
      </div>
    </div>
  );
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="wsResultRow">
      <span className="wsResultLabel">{label}</span>
      <span className="wsResultValue" style={mono ? { fontFamily: 'monospace', fontSize: '12px', overflowWrap: 'break-word' } : undefined}>
        {value}
      </span>
    </div>
  );
}

// ── Video Genres ─────────────────────────────────────────────
const VIDEO_GENRES = [
  'fps','battle_royale','moba','rpg','survival','sandbox',
  'racing','strategy','fighting','puzzle','esports',
  'football','cricket','basketball','tennis','sports',
  'commentary','vlog','unknown',
];

type Highlight = {
  timestamp: number;
  score: number;
  source: string;
  clip_start: number;
  clip_end: number;
  clip_path?: string;
  included: boolean;
};

function parseHighlights(job: Job): Highlight[] {
  let timestamps: Omit<Highlight, 'included' | 'clip_path'>[] = [];
  let clipPaths: string[] = [];
  try {
    if (job.highlight_timestamps) timestamps = JSON.parse(job.highlight_timestamps) as typeof timestamps;
  } catch { /* */ }
  try {
    if (job.clip_paths) clipPaths = JSON.parse(job.clip_paths) as string[];
  } catch { /* */ }
  return timestamps.map((h, i) => ({
    ...h,
    clip_start: h.clip_start ?? 0,
    clip_end: h.clip_end ?? 0,
    clip_path: clipPaths[i],
    included: true,
  }));
}

function parseTags(value?: string | null): string[] {
  if (!value) return [];
  try {
    const p = JSON.parse(value);
    if (Array.isArray(p)) return p.map(String).filter(Boolean);
  } catch { /* */ }
  return value.split(',').map((t) => t.trim()).filter(Boolean);
}

function fmtTime(sec: number): string {
  const t = Math.round(sec);
  const m = Math.floor(t / 60);
  const s = t % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}

/** Parse "1:23" or "83.5" → seconds. Returns null on invalid input. */
function parseTime(raw: string): number | null {
  const s = raw.trim();
  const mmss = /^(\d+):(\d{1,2}(?:\.\d+)?)$/.exec(s);
  if (mmss) {
    const val = parseInt(mmss[1], 10) * 60 + parseFloat(mmss[2]);
    return isNaN(val) || val < 0 ? null : val;
  }
  const n = parseFloat(s);
  return isNaN(n) || n < 0 ? null : n;
}

// ── Clip Timeline ────────────────────────────────────────────
function ClipTimeline({
  clips,
  duration,
  currentTime,
  onSeek,
}: {
  clips: Highlight[];
  duration: number;
  currentTime: number;
  onSeek: (t: number) => void;
}) {
  if (!duration) return null;
  const pct = (t: number) => `${((t / duration) * 100).toFixed(2)}%`;
  const handleClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const ratio = (e.clientX - rect.left) / rect.width;
    onSeek(ratio * duration);
  };
  return (
    <div className="clipTimeline" onClick={handleClick} title="Click to seek">
      <div className="clipTimelineTrack">
        {clips.map((c, i) => (
          <div
            key={i}
            className={`clipTimelineSegment${!c.included ? ' excluded' : ''}${!c.clip_path ? ' custom' : ''}`}
            style={{ left: pct(c.clip_start), width: pct(c.clip_end - c.clip_start) }}
            title={`Clip ${i + 1}: ${fmtTime(c.clip_start)}–${fmtTime(c.clip_end)}`}
          />
        ))}
        <div
          className="clipTimelinePlayhead"
          style={{ left: pct(currentTime) }}
        />
      </div>
      <div className="clipTimelineLabels">
        <span>{fmtTime(0)}</span>
        <span>{fmtTime(duration)}</span>
      </div>
    </div>
  );
}

// ── Job Workstation ──────────────────────────────────────────
function JobWorkstation({ job: initialJob, onJobUpdate }: { job: Job; onJobUpdate: (j: Job) => void }) {
  const isImage = (initialJob.detected_type ?? '').toUpperCase() === 'IMAGE';
  const isVideo = (initialJob.detected_type ?? '').toUpperCase() === 'VIDEO';

  const [job, setJob] = useState(initialJob);
  const [clips, setClips] = useState<Highlight[]>(() => parseHighlights(initialJob));
  const [genre, setGenre] = useState(initialJob.game_genre ?? 'unknown');
  const [gameTitle, setGameTitle] = useState(initialJob.game_title ?? '');
  const [tags, setTags] = useState<string[]>(() => parseTags(initialJob.ai_tags));
  const [tagInput, setTagInput] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState('');
  const [rebuilding, setRebuilding] = useState(false);
  const [rebuildMsg, setRebuildMsg] = useState('');
  const videoRef = useRef<HTMLVideoElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const BASE = (import.meta as { env?: { VITE_API_BASE?: string } }).env?.VITE_API_BASE ?? 'http://localhost:8000';

  // ── drag state ──
  const [draggingIdx, setDraggingIdx] = useState<number | null>(null);
  const [dragOverIdx, setDragOverIdx] = useState<number | null>(null);

  // ── inline edit state ──
  const [editingClip, setEditingClip] = useState<number | null>(null);
  const [editStart, setEditStart] = useState('');
  const [editEnd, setEditEnd] = useState('');

  // ── add-custom-clip state ──
  const [addStart, setAddStart] = useState('');
  const [addEnd, setAddEnd] = useState('');
  const [addClipError, setAddClipError] = useState('');

  // ── playhead tracking ──
  const [currentTime, setCurrentTime] = useState(0);
  const [videoDuration, setVideoDuration] = useState(0);

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

  const seekTo = (time: number) => {
    if (videoRef.current) videoRef.current.currentTime = time;
  };

  // ── drag handlers ──
  const handleDragStart = (i: number) => setDraggingIdx(i);
  const handleDragOver = (e: React.DragEvent, i: number) => {
    e.preventDefault();
    setDragOverIdx(i);
  };
  const handleDrop = (targetIdx: number) => {
    if (draggingIdx === null || draggingIdx === targetIdx) return;
    setClips((prev) => {
      const next = [...prev];
      const [moved] = next.splice(draggingIdx, 1);
      next.splice(targetIdx, 0, moved);
      return next;
    });
  };
  const handleDragEnd = () => { setDraggingIdx(null); setDragOverIdx(null); };

  // ── inline edit handlers ──
  const startEditClip = (i: number) => {
    setEditingClip(i);
    setEditStart(fmtTime(clips[i].clip_start));
    setEditEnd(fmtTime(clips[i].clip_end));
  };
  const commitEditClip = (i: number) => {
    const s = parseTime(editStart);
    const e = parseTime(editEnd);
    if (s !== null && e !== null && e > s) {
      setClips((prev) => prev.map((c, idx) =>
        idx === i ? { ...c, clip_start: s, clip_end: e } : c,
      ));
    }
    setEditingClip(null);
  };

  // ── add custom clip ──
  const addCustomClip = () => {
    setAddClipError('');
    const s = parseTime(addStart);
    const e = parseTime(addEnd);
    if (s === null || e === null) { setAddClipError('Enter valid times (e.g. 1:23 or 83).'); return; }
    if (e <= s) { setAddClipError('End must be after start.'); return; }
    const dur = videoDuration || job.video_duration || 0;
    if (dur && e > dur) { setAddClipError(`End exceeds video duration (${fmtTime(dur)}).`); return; }
    setClips((prev) => [
      ...prev,
      { timestamp: s, score: 0, source: 'manual', clip_start: s, clip_end: e, included: true },
    ]);
    setAddStart('');
    setAddEnd('');
  };

  const saveMetadata = async () => {
    setSaving(true);
    setSaveMsg('');
    try {
      const updated = await api.updateJobMeta(job.id, {
        game_genre: isVideo ? genre : undefined,
        game_title: isVideo ? gameTitle || undefined : undefined,
        ai_tags: isImage ? JSON.stringify(tags) : undefined,
      });
      setJob(updated);
      onJobUpdate(updated);
      setSaveMsg('Saved.');
    } catch (e) {
      setSaveMsg(e instanceof Error ? e.message : 'Save failed.');
    } finally {
      setSaving(false);
      setTimeout(() => setSaveMsg(''), 3000);
    }
  };

  const startRebuild = async () => {
    const includedClips = clips.filter((c) => c.included);
    const selected = includedClips.filter((c) => c.clip_path).map((c) => c.clip_path!);
    const customRanges = includedClips
      .filter((c) => !c.clip_path)
      .map((c) => ({ start: c.clip_start, end: c.clip_end }));
    if (!selected.length && !customRanges.length) {
      setRebuildMsg('Select at least one clip.');
      return;
    }
    setRebuilding(true);
    setRebuildMsg('Rebuilding reel…');
    try {
      await api.rebuildReel(job.id, selected, customRanges);
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = setInterval(async () => {
        try {
          const updated = await api.job(job.id);
          if (updated.status === 'DONE') {
            clearInterval(pollRef.current!);
            setJob(updated);
            onJobUpdate(updated);
            setRebuilding(false);
            setRebuildMsg('Reel rebuilt!');
          } else if (updated.status === 'FAILED') {
            clearInterval(pollRef.current!);
            setRebuilding(false);
            setRebuildMsg(updated.error_message ?? 'Rebuild failed.');
          }
        } catch { /* retry next tick */ }
      }, 2000);
    } catch (e) {
      setRebuilding(false);
      setRebuildMsg(e instanceof Error ? e.message : 'Rebuild failed.');
    }
  };

  const addTag = () => {
    const t = tagInput.trim();
    if (t && !tags.includes(t)) setTags((prev) => [...prev, t]);
    setTagInput('');
  };

  return (
    <div className="jobWsShell">
      <div className="jobWsNav">
        <button className="jobWsBack" onClick={() => navigate('/')}>← Jobs</button>
        <span className="jobWsFilename">{job.filename}</span>
        <span className={`jobWsStatus jobWsStatus-${job.status.toLowerCase()}`}>{job.status}</span>
      </div>

      {/* ── Video player ── */}
      {isVideo && (
        <div className="jobWsVideoWrap">
          <video
            ref={videoRef}
            className="jobWsVideo"
            controls
            src={api.jobVideoUrl(job.id)}
            preload="metadata"
            onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
            onLoadedMetadata={(e) => setVideoDuration(e.currentTarget.duration)}
          />
        </div>
      )}

      {/* ── Image preview ── */}
      {isImage && job.image_url && (
        <div className="jobWsImageWrap">
          <img className="jobWsImage" src={`${BASE}${job.image_url}`} alt={job.filename} />
        </div>
      )}

      <div className="jobWsColumns">

        {/* ── Clips panel (video only) ── */}
        {isVideo && (
          <section className="jobWsSection">
            <h3>Highlight Clips</h3>
            <p className="jobWsSectionHint">
              Drag ⠿ to reorder · click time to edit · toggle to include/exclude · add manual clips below.
            </p>

            {/* ── Timeline ── */}
            {(videoDuration || job.video_duration) ? (
              <ClipTimeline
                clips={clips}
                duration={videoDuration || (job.video_duration ?? 0)}
                currentTime={currentTime}
                onSeek={seekTo}
              />
            ) : null}

            {/* ── Clip cards ── */}
            {clips.length > 0 ? (
              <div className="clipList">
                {clips.map((clip, i) => (
                  <div
                    key={i}
                    draggable
                    onDragStart={() => handleDragStart(i)}
                    onDragOver={(e) => handleDragOver(e, i)}
                    onDrop={() => handleDrop(i)}
                    onDragEnd={handleDragEnd}
                    className={[
                      'clipCard',
                      clip.included ? '' : 'clipCardOff',
                      draggingIdx === i ? 'dragging' : '',
                      dragOverIdx === i && draggingIdx !== i ? 'dragOver' : '',
                    ].filter(Boolean).join(' ')}
                  >
                    <span className="clipDragHandle" title="Drag to reorder">⠿</span>

                    <label className="clipToggleWrap">
                      <input
                        type="checkbox"
                        checked={clip.included}
                        onChange={() => setClips((prev) => prev.map((c, idx) =>
                          idx === i ? { ...c, included: !c.included } : c,
                        ))}
                      />
                      <span className="clipIndex">
                        Clip {i + 1}
                        {!clip.clip_path && <span className="clipCustomBadge">manual</span>}
                      </span>
                    </label>

                    {clip.score > 0 && <span className="clipScore">{clip.score}pts</span>}

                    {/* ── Time display / inline edit ── */}
                    {editingClip === i ? (
                      <div className="clipTimeEditRow">
                        <input
                          className="clipTimeInput"
                          value={editStart}
                          onChange={(e) => setEditStart(e.target.value)}
                          onBlur={() => commitEditClip(i)}
                          onKeyDown={(e) => { if (e.key === 'Enter') commitEditClip(i); if (e.key === 'Escape') setEditingClip(null); }}
                          autoFocus
                          aria-label="Clip start"
                        />
                        <span className="clipTimeSep">–</span>
                        <input
                          className="clipTimeInput"
                          value={editEnd}
                          onChange={(e) => setEditEnd(e.target.value)}
                          onBlur={() => commitEditClip(i)}
                          onKeyDown={(e) => { if (e.key === 'Enter') commitEditClip(i); if (e.key === 'Escape') setEditingClip(null); }}
                          aria-label="Clip end"
                        />
                        <span className="clipDuration">{(clip.clip_end - clip.clip_start).toFixed(1)}s</span>
                      </div>
                    ) : (
                      <div className="clipTimes">
                        <button
                          className="clipSeekBtn"
                          onClick={() => seekTo(clip.clip_start)}
                          title="Seek to clip start"
                        >
                          ▶ {fmtTime(clip.clip_start)} – {fmtTime(clip.clip_end)}
                        </button>
                        <button
                          className="clipEditTimeBtn"
                          onClick={() => startEditClip(i)}
                          title="Edit times"
                        >✎</button>
                        <span className="clipDuration">{(clip.clip_end - clip.clip_start).toFixed(1)}s</span>
                      </div>
                    )}

                    {/* remove button */}
                    <button
                      className="clipRemoveBtn"
                      title="Remove clip"
                      onClick={() => setClips((prev) => prev.filter((_, idx) => idx !== i))}
                    >✕</button>
                  </div>
                ))}
              </div>
            ) : (
              <p className="jobWsSectionHint" style={{ opacity: 0.5 }}>No clips yet. Add one below.</p>
            )}

            {/* ── Add Custom Clip ── */}
            <div className="addClipForm">
              <div className="addClipTitle">＋ Add Custom Clip</div>
              <div className="addClipInputs">
                <div className="addClipField">
                  <label>Start</label>
                  <input
                    className="clipTimeInput"
                    placeholder="0:00"
                    value={addStart}
                    onChange={(e) => { setAddStart(e.target.value); setAddClipError(''); }}
                  />
                  <button
                    className="clipUseCurrentBtn"
                    title="Use current playhead position"
                    onClick={() => setAddStart(fmtTime(currentTime))}
                  >▶ Use current</button>
                </div>
                <div className="addClipField">
                  <label>End</label>
                  <input
                    className="clipTimeInput"
                    placeholder="0:30"
                    value={addEnd}
                    onChange={(e) => { setAddEnd(e.target.value); setAddClipError(''); }}
                  />
                  <button
                    className="clipUseCurrentBtn"
                    title="Use current playhead position"
                    onClick={() => setAddEnd(fmtTime(currentTime))}
                  >▶ Use current</button>
                </div>
                <button
                  className="btnPrimary addClipSubmitBtn"
                  onClick={addCustomClip}
                  disabled={!addStart || !addEnd}
                >Add Clip</button>
              </div>
              {addClipError && <div className="addClipError">{addClipError}</div>}
            </div>

            {/* ── Rebuild actions ── */}
            <div className="jobWsSectionActions">
              <button
                className="btnPrimary"
                onClick={() => void startRebuild()}
                disabled={rebuilding || !clips.some((c) => c.included)}
              >
                {rebuilding ? 'Rebuilding…' : '🎞 Rebuild Reel'}
              </button>
              {rebuildMsg && (
                <span className={`jobWsMsg${rebuildMsg.toLowerCase().includes('fail') || rebuildMsg.includes('Select') ? ' jobWsMsgErr' : ''}`}>
                  {rebuildMsg}
                </span>
              )}
            </div>
            {job.output_path && (
              <a className="wsDownloadLink" href={`${BASE}/jobs/${job.id}/download`} download>
                ⬇ Download Current Reel
              </a>
            )}
          </section>
        )}

        {/* ── Video metadata panel ── */}
        {isVideo && (
          <section className="jobWsSection">
            <h3>Video Metadata</h3>
            <div className="jobWsMeta">
              <label>
                <span>Genre</span>
                <select value={genre} onChange={(e) => setGenre(e.target.value)}>
                  {VIDEO_GENRES.map((g) => (
                    <option key={g} value={g}>{g.replace(/_/g, ' ')}</option>
                  ))}
                </select>
              </label>
              <label>
                <span>Game / Title</span>
                <input
                  type="text"
                  value={gameTitle}
                  onChange={(e) => setGameTitle(e.target.value)}
                  placeholder="e.g. Valorant, CS2, Warzone…"
                />
              </label>
            </div>
            {job.transcript && (
              <div className="jobWsTranscript">
                <span>Transcript</span>
                <p>{job.transcript.slice(0, 500)}{job.transcript.length > 500 ? '…' : ''}</p>
              </div>
            )}
            <div className="jobWsSectionActions">
              <button onClick={() => void saveMetadata()} disabled={saving}>
                {saving ? 'Saving…' : 'Save Changes'}
              </button>
              {saveMsg && <span className="jobWsMsg">{saveMsg}</span>}
            </div>
          </section>
        )}

        {/* ── Image metadata panel ── */}
        {isImage && (
          <section className="jobWsSection">
            <h3>Image Metadata</h3>
            <div className="jobWsMeta">
              <label>
                <span>Category</span>
                <input type="text" value={job.ai_category ?? ''} readOnly style={{ opacity: 0.6 }} />
              </label>
              <label>
                <span>Tags</span>
                <div className="tagEditor">
                  {tags.map((t) => (
                    <span key={t} className="tagChip">
                      {t}
                      <button onClick={() => setTags((prev) => prev.filter((x) => x !== t))}>✕</button>
                    </span>
                  ))}
                  <input
                    className="tagInput"
                    type="text"
                    value={tagInput}
                    onChange={(e) => setTagInput(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); addTag(); } }}
                    placeholder="Add tag…"
                  />
                </div>
              </label>
              {job.ai_summary && (
                <label>
                  <span>Summary</span>
                  <textarea rows={3} value={job.ai_summary} readOnly style={{ opacity: 0.6, resize: 'none' }} />
                </label>
              )}
            </div>
            <div className="jobWsSectionActions">
              <button onClick={() => void saveMetadata()} disabled={saving}>
                {saving ? 'Saving…' : 'Save Changes'}
              </button>
              {saveMsg && <span className="jobWsMsg">{saveMsg}</span>}
            </div>
          </section>
        )}

      </div>
    </div>
  );
}
