import type { ReactNode } from "react";

import { AppChrome } from "./_components/AppChrome";

type AppLayoutProps = {
  children: ReactNode;
};

export default function AppLayout({ children }: AppLayoutProps) {
  return <AppChrome>{children}</AppChrome>;
}
