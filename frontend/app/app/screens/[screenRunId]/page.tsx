import { ScreenRunDetailView } from "./ScreenRunDetailView";


type ScreenRunDetailPageProps = {
  params: Promise<{ screenRunId: string }>;
};


export default async function ScreenRunDetailPage({ params }: ScreenRunDetailPageProps) {
  const { screenRunId } = await params;
  return <ScreenRunDetailView screenRunId={Number(screenRunId)} />;
}

