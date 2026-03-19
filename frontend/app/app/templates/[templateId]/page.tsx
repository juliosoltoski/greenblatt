import { TemplateDetailView } from "./TemplateDetailView";


type TemplateDetailPageProps = {
  params: Promise<{ templateId: string }>;
};


export default async function TemplateDetailPage({ params }: TemplateDetailPageProps) {
  const { templateId } = await params;
  return <TemplateDetailView templateId={Number(templateId)} />;
}
