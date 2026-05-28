import { useState } from 'react';
import { api, type Job } from '../api';
import { navigate } from '../navigation';
import { StatusBadge } from './StatusBadge';

const BASE = (import.meta as { env?: { VITE_API_BASE?: string } }).env?.VITE_API_BASE ?? 'http://localhost:8000';

type Props = {
  job: Job | null;
  onClose: () => void;
  onDelete?: (jobId: number) => void;
};

function fmt(v?: string | number | null, fallback = '—'): string {
  if (v == null || v === '') return fallback;
  return String(v);
}

function fmtDuration(secs?: number | null): string {
  if (!secs) return '—';
  const t = Math.round(secs);
  const m = Math.floor(t / 60);
  const s = t % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

function parseTags(v?: string | null): string {
  if (!v) return '—';
  try {
    const p = JSON.parse(v);
    if (Array.isArray(p)) return p.join(', ') || '—';
  } catch { /* */ }
  return v;
}

function Row({ label, value, mono, pre }: { label: string; value: string; mono?: boolean; pre?: boolean }) {
  return (
    <div className="detailRow">
      <span className="detailLabel">{label}</span>
      <span
        className="detailValue"
        style={{
          fontFamily: mono ? 'var(--font-mono, monospace)' : undefined,
          fontSize: mono ? '11px' : undefined,
          whiteSpace: pre ? 'pre-wrap' : undefined,
          maxHeight: pre ? '100px' : undefined,
          overflowY: pre ? 'auto' : undefined,
          display: pre ? 'block' : undefined,
        }}
      >
        {value}
      </span>
    </div>
  );
}

export function JobDetail({ job, onClose, onDelete }: Props) {
  const [imgError, setImgError] = useState(false);
  const [copied, setCopied] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const handleDelete = async () => {
    if (!job) return;
    if (!window.confirm(`Delete job #${job.id}?`)) return;
    setDeleting(true);
    try {
      await api.deleteJob(job.id);
      onDelete?.(job.id);
      onClose();
    } catch {
      setDeleting(false);
    }
  };

  if (!job) return null;

  const isImg = (job.detected_type || '').toUpperCase() === 'IMAGE';
  const isVid = (job.detected_type || '').toUpperCase() === 'VIDEO';
  const previewSrc = `${BASE}/jobs/${job.id}/image`;

  const copyPath = async (path: string) => {
    try { await navigator.clipboard.writeText(path); } catch { /* */ }
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  return (
    <div className="modalOverlay" onClick={onClose} role="presentation">
      <section
        className="jobModal"
        role="dialog"
        aria-modal="true"
        aria-label={`Job ${job.id}`}
        onClick={(e) => e.stopPropagation()}
      >
        <button className="modalCloseButton" type="button" aria-label="Close" onClick={onClose}>✕</button>

        {/* ── Header ── */}
        <div className="detailHeader">
          <div className="detailFilename" title={job.filename}>{job.filename}</div>
          <div className="detailMeta">
            <StatusBadge status={job.status} />
            {job.detected_type && <span className="typeBadge">{job.detected_type}</span>}
            {isVid && job.game_genre && job.game_genre !== 'unknown' && (
              <span className="genreBadge">{job.game_genre.replace(/_/g, ' ')}</span>
            )}
            {isVid && job.game_title && (
              <span className="detailGameTitle">{job.game_title}</span>
            )}
            <span className="detailId">#{job.id}</span>
          </div>
        </div>

        {/* ── Image preview ── */}
        {isImg && !imgError && (
          <img
            className="detailImage"
            src={previewSrc}
            alt={job.filename}
            onError={() => setImgError(true)}
          />
        )}
        {isImg && imgError && (
          <div className="detailImagePlaceholder">
            <span>🖼</span>
            <span>Preview unavailable</span>
          </div>
        )}

        {/* ── Video placeholder ── */}
        {isVid && (
          <div className="detailVideoPlaceholder">
            <span>🎬</span>
            <span>{fmtDuration(job.video_duration)}</span>
          </div>
        )}

        {/* ── Fields ── */}
        <div className="detailFields">
          {isImg && (
            <>
              <Row label="Category" value={fmt(job.ai_category)} />
              <Row label="Tags"     value={parseTags(job.ai_tags)} />
              <Row label="Summary"  value={fmt(job.ai_summary)} />
              {job.blur_score != null && (
                <Row label="Blur score" value={`${job.blur_score.toFixed(1)} ${job.blur_score < 100 ? '· blurry' : '· sharp'}`} />
              )}
            </>
          )}
          {isVid && (
            <>
              <Row label="Duration"   value={fmtDuration(job.video_duration)} />
              <Row label="Game"       value={fmt(job.game_title)} />
              <Row label="Genre"      value={fmt(job.game_genre)} />
              {job.reel_path  && <Row label="Reel"      value={job.reel_path}  mono />}
              {job.srt_path   && <Row label="Subtitles" value={job.srt_path}   mono />}
              {job.transcript && <Row label="Transcript" value={job.transcript.slice(0, 400) + (job.transcript.length > 400 ? '…' : '')} pre />}
            </>
          )}

          <Row label="Source"  value={job.source_path} mono />
          <Row label="Created" value={fmt(job.created_at)} />
          {job.error_message && <Row label="Error" value={job.error_message} />}
        </div>

        {/* ── Output path ── */}
        {job.output_path && (
          <div className="detailOutput">
            <span className="detailOutputLabel">Output</span>
            <code className="detailOutputPath">{job.output_path}</code>
            <button
              className="detailCopyBtn"
              onClick={() => void copyPath(job.output_path!)}
            >
              {copied ? '✓ Copied' : '⎘ Copy path'}
            </button>
          </div>
        )}

        {/* ── Footer actions ── */}
        <div className="detailFooterActions">
          {job.status === 'DONE' && (
            <button
              className="btnPrimary wsOpenBtnLarge"
              onClick={() => navigate(`/workstation/job/${job.id}`)}
            >
              ✦ Open in Workstation
            </button>
          )}
          <button
            className="compactButton dangerButton detailDeleteBtn"
            onClick={() => void handleDelete()}
            disabled={deleting}
          >
            {deleting ? 'Deleting…' : 'Delete Job'}
          </button>
        </div>
      </section>
    </div>
  );
}
