import { ScreenHub } from "./ScreenHub";


type ScreensPageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};


export default async function ScreensPage({ searchParams }: ScreensPageProps) {
  const resolved = await searchParams;
  return (
    <ScreenHub
      templateId={typeof resolved.template_id === "string" ? Number(resolved.template_id) : null}
      draftScreenRunId={typeof resolved.draft_screen_run_id === "string" ? Number(resolved.draft_screen_run_id) : null}
    />
  );
}
