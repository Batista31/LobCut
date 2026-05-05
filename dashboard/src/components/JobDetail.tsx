import { type Job } from '../api';
import { StatusBadge } from './StatusBadge';

const API_BASE = 'http://localhost:8000';

type Props = {
  job: Job | null;
  onClose: () => void;
};

function excerpt(value?: string | null) {
  if (!value) return '-';
  return value.length > 300 ? `${value.slice(0, 300)}...` : value;
}

function isImage(job: Job) {
  return (job.detected_type || '').toUpperCase() === 'IMAGE';
}

function isVideo(job: Job) {
  return (job.detected_type || '').toUpperCase() === 'VIDEO';
}

export function JobDetail({ job, onClose }: Props) {
  if (!job) return null;

  return (
    <div className="modalOverlay" onClick={onClose} role="presentation">
      <section className="jobModal" role="dialog" aria-modal="true" aria-label={`Job ${job.id}`} onClick={(event) => event.stopPropagation()}>
        <button className="modalCloseButton" type="button" aria-label="Close" onClick={onClose}>x</button>
        <h2>{job.filename}</h2>
        {isImage(job) ? (
          <img className="detailImage" src={`${API_BASE}/jobs/${job.id}/preview`} alt={job.filename} />
        ) : null}
        {isVideo(job) ? (
          <div className="videoPreviewIcon" aria-hidden="true" />
        ) : null}
        {isVideo(job) ? (
          <dl>
            <dt>Filename</dt><dd>{job.filename}</dd>
            <dt>Status</dt><dd><StatusBadge status={job.status} /></dd>
            <dt>Transcript</dt><dd>{excerpt(job.transcript)}</dd>
            <dt>Game title</dt><dd>{job.game_title || '-'}</dd>
            <dt>Game genre</dt><dd>{job.game_genre || '-'}</dd>
            <dt>Duration</dt><dd>{job.video_duration ?? '-'}</dd>
            <dt>Created</dt><dd>{job.created_at}</dd>
          </dl>
        ) : (
          <dl>
            <dt>Filename</dt><dd>{job.filename}</dd>
            <dt>Status</dt><dd><StatusBadge status={job.status} /></dd>
            <dt>Category</dt><dd>{job.ai_category || '-'}</dd>
            <dt>Tags</dt><dd>{job.ai_tags || '-'}</dd>
            <dt>Summary</dt><dd>{job.ai_summary || '-'}</dd>
            <dt>Blur score</dt><dd>{job.blur_score ?? '-'}</dd>
            <dt>Created</dt><dd>{job.created_at}</dd>
            <dt>Updated</dt><dd>{job.updated_at}</dd>
          </dl>
        )}
      </section>
    </div>
  );
}
