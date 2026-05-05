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
      <span className={`liveDot ${polling ? 'active' : ''}`} />
      <div><strong>{jobs.length}</strong><span>Total</span></div>
      <div><strong>{done}</strong><span>Done</span></div>
      <div><strong>{failed}</strong><span>Failed</span></div>
      <div><strong>{processing}</strong><span>Processing</span></div>
    </section>
  );
}
