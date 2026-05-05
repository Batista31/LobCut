import { api, type Job } from '../api';
import { StatusBadge } from './StatusBadge';

const API_BASE = 'http://localhost:8000';

type Props = {
  jobs: Job[];
  loading: boolean;
  polling: boolean;
  refresh: () => Promise<void>;
  onSelect: (job: Job) => void;
  selectedId: number | null;
};

export function JobsTable({ jobs, loading, polling, refresh, onSelect, selectedId }: Props) {
  const retry = async (job: Job) => {
    await api.retryJob(job.id);
    await refresh();
  };

  const remove = async (job: Job) => {
    await api.deleteJob(job.id);
    await refresh();
  };

  const imageSrc = (job: Job) => job.image_url ? `${API_BASE}${job.image_url}` : null;

  return (
    <section className="tableSection">
      <div className="tableHeader">
        <h1>Jobs</h1>
        <span><i className={`liveDot ${polling ? 'active' : ''}`} /> live</span>
      </div>
      <table>
        <thead>
          <tr>
            <th>File</th>
            <th>Preview</th>
            <th>Type</th>
            <th>Status</th>
            <th>Category</th>
            <th>Location</th>
            <th>Created</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <tr><td colSpan={8}>Loading jobs...</td></tr>
          ) : jobs.length === 0 ? (
            <tr><td colSpan={8}>No jobs yet.</td></tr>
          ) : (
            jobs.map((job) => (
              <tr
                key={job.id}
                className={selectedId === job.id ? 'selected' : ''}
                onClick={() => onSelect(job)}
              >
                <td><code>#{job.id}</code> {job.filename}</td>
                <td>
                  {imageSrc(job) ? (
                    <img className="jobThumb" src={imageSrc(job) ?? ''} alt="" loading="lazy" />
                  ) : (
                    <span className="emptyPreview">-</span>
                  )}
                </td>
                <td><span className="typeBadge">{job.detected_type || 'UNKNOWN'}</span></td>
                <td><StatusBadge status={job.status} /></td>
                <td>
                  {job.ai_category || '-'}
                  {job.error_message ? <div className="errorText">{job.error_message}</div> : null}
                </td>
                <td><code className="pathText">{job.output_path || job.source_path}</code></td>
                <td>{job.created_at}</td>
                <td>
                  <button type="button" onClick={(event) => { event.stopPropagation(); void retry(job); }}>Retry</button>
                  <button type="button" className="dangerButton" onClick={(event) => { event.stopPropagation(); void remove(job); }}>Delete</button>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </section>
  );
}
