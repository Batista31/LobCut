import { useState } from 'react';
import { api, type Job } from '../api';
import { StatusBadge } from './StatusBadge';

const API_BASE = 'http://localhost:8000';

type LobCutWindow = Window & {
  lobcut?: {
    openOutputFolder?: (filePath: string) => void;
  };
};

type Props = {
  jobs: Job[];
  loading: boolean;
  polling: boolean;
  refresh: () => Promise<void>;
  onDeleteLocal: (jobId: number) => void;
  onToast: (message: string) => void;
  onSelect: (job: Job) => void;
  selectedId: number | null;
};

export function JobsTable({ jobs, loading, polling, refresh, onDeleteLocal, onToast, onSelect, selectedId }: Props) {
  const [openedJobId, setOpenedJobId] = useState<number | null>(null);
  const [outputMessage, setOutputMessage] = useState('');
  const [spinning, setSpinning] = useState(false);

  const openOutput = async (job: Job) => {
    if (!job.output_path) return;
    const lobcut = (window as LobCutWindow).lobcut;
    if (lobcut?.openOutputFolder) {
      lobcut.openOutputFolder(job.output_path);
      setOutputMessage('Opened!');
    } else {
      try {
        await navigator.clipboard.writeText(job.output_path);
      } catch {
        onToast(job.output_path);
      }
      setOutputMessage('Path copied!');
    }
    setOpenedJobId(job.id);
    window.setTimeout(() => setOpenedJobId(null), 2000);
  };

  const handleRefresh = async () => {
    setSpinning(true);
    await refresh();
    window.setTimeout(() => setSpinning(false), 600);
  };

  const retry = async (job: Job) => {
    try {
      await api.retryJob(job.id);
      await refresh();
      onToast(`Job #${job.id} queued`);
    } catch (error) {
      onToast(error instanceof Error ? error.message : `Could not retry job #${job.id}`);
    }
  };

  const remove = async (job: Job) => {
    if (!window.confirm(`Delete job #${job.id} and remove from database?`)) {
      return;
    }
    try {
      await api.deleteJob(job.id);
      onDeleteLocal(job.id);
      onToast(`Job #${job.id} deleted`);
    } catch (error) {
      onToast(error instanceof Error ? error.message : `Could not delete job #${job.id}`);
    }
  };

  const previewSrc = (job: Job) => `${API_BASE}/jobs/${job.id}/preview`;
  const isImage = (job: Job) => (job.detected_type || '').toUpperCase() === 'IMAGE';
  const isVideo = (job: Job) => (job.detected_type || '').toUpperCase() === 'VIDEO';
  const doneWithOutput = (job: Job) => job.status === 'DONE' && Boolean(job.output_path);
  const title = (value: unknown) => String(value ?? '-');

  return (
    <section className="tableSection">
      <div className="tableHeader">
        <h1>Jobs</h1>
        <div className="tableHeaderControls">
          <button
            type="button"
            className={`refreshButton ${spinning ? 'spinning' : ''}`}
            onClick={() => void handleRefresh()}
            title="Refresh jobs"
            aria-label="Refresh jobs"
          >
            ↻
          </button>
          <span><i className={`liveDot ${polling ? 'active' : ''}`} /> live</span>
        </div>
      </div>
      <table className="jobsTable">
        <colgroup>
          <col style={{ width: '4%' }} />
          <col style={{ width: '16%' }} />
          <col style={{ width: '6%' }} />
          <col style={{ width: '6%' }} />
          <col style={{ width: '8%' }} />
          <col style={{ width: '8%' }} />
          <col style={{ width: '18%' }} />
          <col style={{ width: '10%' }} />
          <col style={{ width: '8%' }} />
          <col style={{ width: '16%' }} />
        </colgroup>
        <thead>
          <tr>
            <th title="ID">ID</th>
            <th title="Filename">Filename</th>
            <th title="User">User</th>
            <th title="Type">Type</th>
            <th title="Status">Status</th>
            <th title="Category">Category</th>
            <th title="Path">Path</th>
            <th title="Date">Date</th>
            <th title="Actions">Actions</th>
            <th title="Output">Output</th>
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <tr><td colSpan={10}>Loading jobs...</td></tr>
          ) : jobs.length === 0 ? (
            <tr><td colSpan={10}>No jobs yet.</td></tr>
          ) : (
            jobs.map((job) => (
              <tr
                key={job.id}
                className={selectedId === job.id ? 'selected' : ''}
                onClick={() => onSelect(job)}
              >
                <td title={title(job.id)}><code>#{job.id}</code></td>
                <td title={job.filename}>{job.filename}</td>
                <td title={job.user_id}>{job.user_id}</td>
                <td title={title(job.detected_type || 'UNKNOWN')}><span className="typeBadge">{job.detected_type || 'UNKNOWN'}</span></td>
                <td title={job.status}><StatusBadge status={job.status} /></td>
                <td title={title(job.ai_category || job.error_message || '-')}>
                  {job.ai_category || '-'}
                  {job.error_message ? <div className="errorText">{job.error_message}</div> : null}
                </td>
                <td title={job.source_path}><code className="pathText">{job.source_path}</code></td>
                <td title={job.created_at}>{job.created_at}</td>
                <td title="Retry or delete this job">
                  <div className="actionGroup">
                    <button type="button" className="compactButton" title="Retry job" onClick={(event) => { event.stopPropagation(); void retry(job); }}>Retry</button>
                    <button type="button" className="compactButton dangerButton" title="Delete job" onClick={(event) => { event.stopPropagation(); void remove(job); }}>Del</button>
                  </div>
                </td>
                <td title={title(job.output_path || '-')}>
                  {doneWithOutput(job) ? (
                    <button type="button" className="outputButton" onClick={(event) => { event.stopPropagation(); void openOutput(job); }}>
                      {isImage(job) ? <img className="outputThumb" src={previewSrc(job)} alt="" loading="lazy" /> : null}
                      {isVideo(job) ? <span className="filmIcon" aria-hidden="true" /> : null}
                      <span className="outputLabel">Open Output</span>
                      {openedJobId === job.id ? <span className="copiedTooltip">{outputMessage}</span> : null}
                    </button>
                  ) : (
                    <span className="emptyPreview">-</span>
                  )}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </section>
  );
}
