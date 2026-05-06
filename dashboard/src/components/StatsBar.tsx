import { type Job } from '../api';

type Props = {
  jobs: Job[];
  polling: boolean;
};

export function StatsBar({ jobs, polling }: Props) {
  const done = jobs.filter((job) => job.status === 'DONE').length;
  const failed = jobs.filter((job) => job.status === 'FAILED').length;
  const processing = jobs.filter((job) => job.status === 'PROCESSING').length;

  return (
    <section className="statsBar">
      <p className="jobSummary">
        {jobs.length} jobs &middot; {done} done &middot; {failed} failed &middot; {processing} processing
      </p>
      <div><strong>{jobs.length}</strong><span>Total</span></div>
      <div><strong>{done}</strong><span>Done</span></div>
      <div><strong>{failed}</strong><span>Failed</span></div>
      <div><strong>{processing}</strong><span>Active</span></div>
    </section>
  );
}
