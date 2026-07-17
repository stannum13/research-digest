import { ReactNode } from "react";
import { motion, useScroll, useTransform } from "framer-motion";

import { Sidebar } from "./Sidebar";

export function AppShell({ children }: { children: ReactNode }) {
  const { scrollYProgress } = useScroll();
  const width = useTransform(scrollYProgress, [0, 1], ["0%", "100%"]);

  return (
    <div className="app-bg paper-noise min-h-screen">
      <motion.div
        className="fixed left-0 top-0 z-40 h-0.5 bg-[rgba(183,119,85,0.68)] md:left-[264px]"
        style={{ width }}
      />
      <Sidebar />
      <main className="relative z-10 min-h-screen px-4 pb-24 pt-24 sm:px-6 md:ml-[264px] md:px-10 md:pt-10">
        <div className="mx-auto max-w-[760px]">{children}</div>
      </main>
    </div>
  );
}
