import { BacktestHub } from "./BacktestHub";


type BacktestsPageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};


export default async function BacktestsPage({ searchParams }: BacktestsPageProps) {
  const resolved = await searchParams;
  return (
    <BacktestHub
      templateId={typeof resolved.template_id === "string" ? Number(resolved.template_id) : null}
      draftBacktestRunId={typeof resolved.draft_backtest_run_id === "string" ? Number(resolved.draft_backtest_run_id) : null}
    />
  );
}
