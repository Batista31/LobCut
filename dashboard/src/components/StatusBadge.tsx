type Props = {
  status: string;
};

export function StatusBadge({ status }: Props) {
  const key = status.toLowerCase().replace(/[^a-z0-9]+/g, '-');
  return <span className={`statusBadge ${key}`}>{status}</span>;
}
