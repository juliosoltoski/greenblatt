import { BacktestRunDetailView } from "./BacktestRunDetailView";


type BacktestRunDetailPageProps = {
  params: Promise<{ backtestRunId: string }>;
};


export default async function BacktestRunDetailPage({ params }: BacktestRunDetailPageProps) {
  const { backtestRunId } = await params;
  return <BacktestRunDetailView backtestRunId={Number(backtestRunId)} />;
}

