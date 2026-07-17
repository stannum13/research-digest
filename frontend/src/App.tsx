import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { SynthesisSelectionProvider } from "./context/SynthesisSelectionProvider";
import { ArchivePage } from "./routes/ArchivePage";
import { FeedPage } from "./routes/FeedPage";
import { SearchPage } from "./routes/SearchPage";
import { SavedPage } from "./routes/SavedPage";
import { StatusPage } from "./routes/StatusPage";
import { SynthesisWorkbenchPage } from "./routes/SynthesisWorkbenchPage";

export function App() {
  return (
    <SynthesisSelectionProvider>
      <AppShell>
        <Routes>
          <Route path="/" element={<FeedPage title="Daily Feed" />} />
          <Route path="/saved" element={<SavedPage />} />
          <Route path="/quantum" element={<FeedPage title="Quantum" category="quant-ph" />} />
          <Route path="/ml" element={<FeedPage title="ML" category="cs.LG,stat.ML" />} />
          <Route path="/ai" element={<FeedPage title="AI" category="cs.AI,cs.CL,cs.CV" />} />
          <Route path="/archive" element={<ArchivePage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/synthesis" element={<SynthesisWorkbenchPage />} />
          <Route path="/status" element={<StatusPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AppShell>
    </SynthesisSelectionProvider>
  );
}
