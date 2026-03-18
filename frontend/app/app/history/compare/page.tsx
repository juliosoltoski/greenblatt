import { HistoryCompareView } from "./HistoryCompareView";


type HistoryComparePageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};


export default async function HistoryComparePage({ searchParams }: HistoryComparePageProps) {
  const resolved = await searchParams;
  const kind = typeof resolved.kind === "string" ? resolved.kind : "screen";
  const left = typeof resolved.left === "string" ? Number(resolved.left) : NaN;
  const right = typeof resolved.right === "string" ? Number(resolved.right) : NaN;

  return <HistoryCompareView kind={kind === "backtest" ? "backtest" : "screen"} leftId={left} rightId={right} />;
}

