import { UniverseDetailView } from "./UniverseDetailView";


type UniverseDetailPageProps = {
  params: Promise<{ universeId: string }>;
};


export default async function UniverseDetailPage({ params }: UniverseDetailPageProps) {
  const { universeId } = await params;
  return <UniverseDetailView universeId={Number(universeId)} />;
}
