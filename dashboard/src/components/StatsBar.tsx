import { type Job } from '../api';

type Props = {
  jobs: Job[];
  polling: boolean;
};

export function StatsBar({ jobs, polling }: Props) {
  const done       = jobs.filter((j) => j.status === 'DONE').length;
  const failed     = jobs.filter((j) => j.status === 'FAILED').length;
  const active     = jobs.filter((j) =>
    ['PROCESSING', 'ACTIVE', 'RUNNING', 'QUEUED', 'PENDING'].includes(j.status),
  ).length;

  return (
    <section className="statsBar">
      <StatCard value={jobs.length} label="Total"  />
      <StatCard value={done}        label="Done"    accent="success" />
      <StatCard value={active}      label="Active"  accent="warning" dimIfZero />
      <StatCard value={failed}      label="Failed"  accent="error"   dimIfZero />
      <div className="statsLiveChip">
        <i className={`liveDot ${polling ? 'active' : ''}`} />
        <span>{polling ? 'polling' : 'idle'}</span>
      </div>
    </section>
  );
}

function StatCard({
  value,
  label,
  accent,
  dimIfZero,
}: {
  value: number;
  label: string;
  accent?: 'success' | 'warning' | 'error';
  dimIfZero?: boolean;
}) {
  const dim = dimIfZero && value === 0;
  return (
    <div
      className={[
        'statsCard',
        accent ? `statsCard-${accent}` : '',
        dim ? 'statsCard-dim' : '',
      ].filter(Boolean).join(' ')}
    >
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}
