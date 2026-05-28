import { useMemo, useState } from 'react';
import { api, type Job } from '../api';
import { navigate } from '../navigation';
import { StatusBadge } from './StatusBadge';

const API_BASE = (import.meta as { env?: { VITE_API_BASE?: string } }).env?.VITE_API_BASE ?? 'http://localhost:8000';

/** Infer what action produced this job's output, for the info badge. */
function getActionBadge(job: Job): { label: string; cls: string } | null {
  if (job.status !== 'DONE') return null;
  const type = (job.detected_type ?? '').toUpperCase();
  if (type === 'IMAGE')  return { label: 'Classify',   cls: 'actionBadge-classify' };
  if (type !== 'VIDEO')  return null;
  if (job.reel_path)     return { label: 'Reel',        cls: 'actionBadge-reel' };
  if (job.srt_path)      return { label: 'Subtitles',   cls: 'actionBadge-subtitles' };
  if (job.output_path)   return { label: 'Captioned',   cls: 'actionBadge-captioned' };
  return null;
}

type LobCutWindow = Window & {
  lobcut?: { openOutputFolder?: (filePath: string) => void };
};

type SortCol = 'id' | 'filename' | 'status' | 'date';
type SortDir = 'asc' | 'desc';

type StatusFilterKey = 'ALL' | 'ACTIVE' | 'DONE' | 'FAILED';

const STATUS_FILTERS: { key: StatusFilterKey; label: string }[] = [
  { key: 'ALL',    label: 'All' },
  { key: 'ACTIVE', label: 'Active' },
  { key: 'DONE',   label: 'Done' },
  { key: 'FAILED', label: 'Failed' },
];

const ACTIVE_STATUSES = new Set(['PROCESSING', 'ACTIVE', 'RUNNING', 'QUEUED', 'PENDING']);

function matchesStatusFilter(job: Job, filter: StatusFilterKey): boolean {
  if (filter === 'ALL')    return true;
  if (filter === 'ACTIVE') return ACTIVE_STATUSES.has(job.status);
  return job.status === filter;
}

function relativeDate(iso: string): { short: string; full: string } {
  const d = new Date(iso);
  const full = d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
  const ms = Date.now() - d.getTime();
  const mins = Math.floor(ms / 60_000);
  if (mins < 1)  return { short: 'just now', full };
  if (mins < 60) return { short: `${mins}m ago`, full };
  const hrs = Math.floor(mins / 60);
  if (hrs < 24)  return { short: `${hrs}h ago`, full };
  const days = Math.floor(hrs / 24);
  if (days < 7)  return { short: `${days}d ago`, full };
  return { short: d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }), full };
}

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

export function JobsTable({
  jobs, loading, polling, refresh,
  onDeleteLocal, onToast, onSelect, selectedId,
}: Props) {
  const [search,       setSearch]       = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusFilterKey>('ALL');
  const [sortCol,      setSortCol]      = useState<SortCol>('id');
  const [sortDir,      setSortDir]      = useState<SortDir>('desc');
  const [openedJobId,  setOpenedJobId]  = useState<number | null>(null);
  const [outputMsg,    setOutputMsg]    = useState('');
  const [spinning,     setSpinning]     = useState(false);

  /* ── Sort toggle ── */
  const handleSort = (col: SortCol) => {
    if (sortCol === col) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortCol(col);
      setSortDir(col === 'id' || col === 'date' ? 'desc' : 'asc');
    }
  };

  /* ── Filter + sort (memoised) ── */
  const filtered = useMemo(() => {
    let result = jobs.filter((j) => matchesStatusFilter(j, statusFilter));

    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter(
        (j) =>
          j.filename.toLowerCase().includes(q) ||
          j.source_path.toLowerCase().includes(q) ||
          (j.ai_category  ?? '').toLowerCase().includes(q) ||
          (j.game_title   ?? '').toLowerCase().includes(q) ||
          (j.game_genre   ?? '').toLowerCase().includes(q) ||
          j.status.toLowerCase().includes(q) ||
          String(j.id).includes(q),
      );
    }

    result = [...result].sort((a, b) => {
      let va: string | number;
      let vb: string | number;
      switch (sortCol) {
        case 'id':       va = a.id;          vb = b.id;          break;
        case 'filename': va = a.filename;    vb = b.filename;    break;
        case 'status':   va = a.status;      vb = b.status;      break;
        case 'date':     va = a.created_at;  vb = b.created_at;  break;
        default:         va = a.id;          vb = b.id;
      }
      if (va < vb) return sortDir === 'asc' ? -1 : 1;
      if (va > vb) return sortDir === 'asc' ?  1 : -1;
      return 0;
    });

    return result;
  }, [jobs, search, statusFilter, sortCol, sortDir]);

  /* ── Status counts for chips ── */
  const counts = useMemo(
    () => ({
      ALL:    jobs.length,
      ACTIVE: jobs.filter((j) => ACTIVE_STATUSES.has(j.status)).length,
      DONE:   jobs.filter((j) => j.status === 'DONE').length,
      FAILED: jobs.filter((j) => j.status === 'FAILED').length,
    }),
    [jobs],
  );

  /* ── Actions ── */
  const openOutput = async (job: Job) => {
    if (!job.output_path) return;
    const lobcut = (window as LobCutWindow).lobcut;
    if (lobcut?.openOutputFolder) {
      lobcut.openOutputFolder(job.output_path);
      setOutputMsg('Opened!');
    } else {
      try { await navigator.clipboard.writeText(job.output_path); }
      catch { onToast(job.output_path); }
      setOutputMsg('Path copied!');
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
    } catch (err) {
      onToast(err instanceof Error ? err.message : `Could not retry job #${job.id}`);
    }
  };

  const remove = async (job: Job) => {
    if (!window.confirm(`Delete job #${job.id} and remove from database?`)) return;
    try {
      await api.deleteJob(job.id);
      onDeleteLocal(job.id);
      onToast(`Job #${job.id} deleted`);
    } catch (err) {
      onToast(err instanceof Error ? err.message : `Could not delete job #${job.id}`);
    }
  };

  /* ── Helpers ── */
  const previewSrc = (job: Job) => `${API_BASE}/jobs/${job.id}/preview`;
  const isImage    = (job: Job) => (job.detected_type ?? '').toUpperCase() === 'IMAGE';
  const isVideo    = (job: Job) => (job.detected_type ?? '').toUpperCase() === 'VIDEO';
  const hasOutput  = (job: Job) => job.status === 'DONE' && Boolean(job.output_path);

  const rowClass = (job: Job) =>
    [
      selectedId === job.id ? 'selected' : '',
      `jobRowStatus-${job.status.toLowerCase()}`,
    ]
      .filter(Boolean)
      .join(' ');

  const SortIcon = ({ col }: { col: SortCol }) => {
    if (sortCol !== col) return <span className="sortIcon sortIconInactive">↕</span>;
    return <span className="sortIcon sortIconActive">{sortDir === 'asc' ? '↑' : '↓'}</span>;
  };

  const hasFilters = search.trim() !== '' || statusFilter !== 'ALL';

  return (
    <section className="tableSection">

      {/* ── Header row ── */}
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

      {/* ── Filter bar ── */}
      <div className="tableFilterBar">
        <div className="tableSearchWrap">
          <span className="tableSearchIcon">⌕</span>
          <input
            className="tableSearchInput"
            type="text"
            placeholder="Search by filename, ID, category…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Search jobs"
          />
          {search && (
            <button
              className="tableSearchClear"
              onClick={() => setSearch('')}
              aria-label="Clear search"
            >
              ✕
            </button>
          )}
        </div>
        <div className="tableFilterChips">
          {STATUS_FILTERS.map(({ key, label }) => (
            <button
              key={key}
              className={[
                'filterChip',
                `filterChip-${key.toLowerCase()}`,
                statusFilter === key ? 'active' : '',
              ].filter(Boolean).join(' ')}
              onClick={() => setStatusFilter(key)}
            >
              {label}
              <span className="filterChipCount">{counts[key]}</span>
            </button>
          ))}
        </div>
      </div>

      {/* ── Table ── */}
      <table className="jobsTable">
        <colgroup>
          <col style={{ width: '52px' }} />
          <col style={{ width: '220px' }} />
          <col style={{ width: '66px' }} />
          <col style={{ width: '92px' }} />
          <col style={{ width: '190px' }} />
          <col style={{ width: '84px' }} />
          <col style={{ width: '140px' }} />
          <col style={{ width: '150px' }} />
        </colgroup>
        <thead>
          <tr>
            <th>
              <button className="sortableHeader" onClick={() => handleSort('id')}>
                ID <SortIcon col="id" />
              </button>
            </th>
            <th>
              <button className="sortableHeader" onClick={() => handleSort('filename')}>
                Filename <SortIcon col="filename" />
              </button>
            </th>
            <th>Type</th>
            <th>
              <button className="sortableHeader" onClick={() => handleSort('status')}>
                Status <SortIcon col="status" />
              </button>
            </th>
            <th>Info</th>
            <th>
              <button className="sortableHeader" onClick={() => handleSort('date')}>
                Date <SortIcon col="date" />
              </button>
            </th>
            <th>Actions</th>
            <th>Output</th>
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <SkeletonRows cols={8} rows={8} />
          ) : filtered.length === 0 ? null : (
            filtered.map((job) => (
              <tr
                key={job.id}
                className={rowClass(job)}
                onClick={() => onSelect(job)}
              >
                <td title={String(job.id)}>
                  <code>#{job.id}</code>
                </td>
                <td title={job.filename}>{job.filename}</td>
                <td>
                  <span className="typeBadge">{job.detected_type ?? 'UNK'}</span>
                </td>
                <td>
                  <StatusBadge status={job.status} />
                </td>
                <td title={job.ai_category ?? job.game_title ?? job.game_genre ?? '—'}>
                  <div className="infoCellWrap">
                    {isImage(job) ? (
                      <span className="infoCellText">{job.ai_category ?? '—'}</span>
                    ) : (
                      <span className="videoGenreCell">
                        {job.game_title && <span className="gameTitle">{job.game_title}</span>}
                        {job.game_genre && job.game_genre !== 'unknown' && (
                          <span className="genreBadge">{job.game_genre.replace(/_/g, ' ')}</span>
                        )}
                        {!job.game_title && (!job.game_genre || job.game_genre === 'unknown') && (
                          <span className="infoCellText">—</span>
                        )}
                      </span>
                    )}
                    {(() => {
                      const b = getActionBadge(job);
                      return b ? <span className={`actionBadge ${b.cls}`}>{b.label}</span> : null;
                    })()}
                    {job.error_message && (
                      <div className="errorText">{job.error_message}</div>
                    )}
                  </div>
                </td>
                <td>
                  {(() => {
                    const { short, full } = relativeDate(job.created_at);
                    return <span className="dateCell" title={full}>{short}</span>;
                  })()}
                </td>
                <td className="actionCell">
                  <div className="actionGroup">
                    {job.status === 'DONE' && (
                      <button
                        type="button"
                        className="compactButton wsOpenBtn"
                        title="Open in Workstation"
                        onClick={(e) => { e.stopPropagation(); navigate(`/workstation/job/${job.id}`); }}
                      >
                        WS
                      </button>
                    )}
                    <button
                      type="button"
                      className="compactButton"
                      title="Retry job"
                      onClick={(e) => { e.stopPropagation(); void retry(job); }}
                    >
                      Retry
                    </button>
                    <button
                      type="button"
                      className="compactButton dangerButton"
                      title="Delete job"
                      onClick={(e) => { e.stopPropagation(); void remove(job); }}
                    >
                      Del
                    </button>
                  </div>
                </td>
                <td className="outputCell" title={job.output_path ?? '—'}>
                  {hasOutput(job) ? (
                    <button
                      type="button"
                      className="outputButton"
                      onClick={(e) => { e.stopPropagation(); void openOutput(job); }}
                    >
                      {isImage(job) && (
                        <img
                          className="outputThumb"
                          src={previewSrc(job)}
                          alt=""
                          loading="lazy"
                          onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }}
                        />
                      )}
                      {isVideo(job) && <span className="filmIcon" aria-hidden="true" />}
                      <span className="outputLabel">
                        {openedJobId === job.id ? outputMsg : 'Open Output'}
                      </span>
                    </button>
                  ) : (
                    <span className="emptyPreview">—</span>
                  )}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      {/* ── Empty states ── */}
      {!loading && filtered.length === 0 && (
        hasFilters ? (
          <div className="tableEmptyState">
            <span className="tableEmptyIcon">◎</span>
            <p className="tableEmptyTitle">No matching jobs</p>
            <p className="tableEmptyDesc">
              {search ? `No jobs found for "${search}"` : `No ${statusFilter.toLowerCase()} jobs`}
              {hasFilters && (
                <button
                  className="tableEmptyClear"
                  onClick={() => { setSearch(''); setStatusFilter('ALL'); }}
                >
                  Clear filters
                </button>
              )}
            </p>
          </div>
        ) : (
          <div className="tableEmptyState">
            <span className="tableEmptyIcon">◈</span>
            <p className="tableEmptyTitle">No jobs yet</p>
            <p className="tableEmptyDesc">
              Drop a file in the Workstation or set up a Watch Folder to start processing.
            </p>
          </div>
        )
      )}
    </section>
  );
}

/* ── Skeleton loading rows ── */
function SkeletonRows({ cols, rows }: { cols: number; rows: number }) {
  return (
    <>
      {Array.from({ length: rows }).map((_, r) => (
        <tr key={r} className="skeletonRow">
          {Array.from({ length: cols }).map((_, c) => (
            <td key={c}>
              <div
                className="skeletonCell"
                style={{ width: `${50 + ((r * 17 + c * 31) % 40)}%`, opacity: 1 - r * 0.09 }}
              />
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}
