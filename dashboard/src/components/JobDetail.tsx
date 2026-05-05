import { type Job } from '../api';
import { StatusBadge } from './StatusBadge';

const API_BASE = 'http://localhost:8000';

type Props = {
  job: Job | null;
  onClose: () => void;
};

function excerpt(value?: string | null) {
  if (!value) return '-';
  return value.length > 200 ? `${value.slice(0, 200)}...` : value;
}

export function JobDetail({ job, onClose }: Props) {
  return (
    <aside className={`detailPanel ${job ? 'open' : ''}`}>
      {job ? (
        <>
          <button className="closeButton" type="button" onClick={onClose}>Close</button>
          <h2>{job.filename}</h2>
          {job.image_url ? (
            <img className="detailImage" src={`${API_BASE}${job.image_url}`} alt="" />
          ) : null}
          <dl>
            <dt>Path</dt><dd><code>{job.source_path}</code></dd>
            <dt>Status</dt><dd><StatusBadge status={job.status} /></dd>
            <dt>Error</dt><dd>{job.error_message || '-'}</dd>
            <dt>Pipeline</dt><dd>{job.pipeline || '-'}</dd>
            <dt>Detected type</dt><dd>{job.detected_type || '-'}</dd>
            <dt>AI category</dt><dd>{job.ai_category || '-'}</dd>
            <dt>Tags</dt><dd>{job.ai_tags || '-'}</dd>
            <dt>Summary</dt><dd>{job.ai_summary || '-'}</dd>
            <dt>Blur score</dt><dd>{job.blur_score ?? '-'}</dd>
            <dt>Output</dt>
            <dd>{job.output_path ? <a href={job.output_path}><code>{job.output_path}</code></a> : '-'}</dd>
            <dt>Transcript</dt><dd>{excerpt(job.transcript)}</dd>
            <dt>Created</dt><dd>{job.created_at}</dd>
            <dt>Updated</dt><dd>{job.updated_at}</dd>
          </dl>
        </>
      ) : null}
    </aside>
  );
}
