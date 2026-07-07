import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import LoginPage from "./auth/LoginPage";
import Layout from "./components/Layout";
import AlertsPage from "./pages/AlertsPage";
import BudgetsPage from "./pages/BudgetsPage";
import CampaignHealthPage from "./pages/CampaignHealthPage";
import KeywordHealthPage from "./pages/KeywordHealthPage";
import OverviewPage from "./pages/OverviewPage";
import PriorityQueuePage from "./pages/PriorityQueuePage";
import ReportsPage from "./pages/ReportsPage";
import SearchTermsPage from "./pages/SearchTermsPage";
import TrendsPage from "./pages/TrendsPage";
import type { ReactNode } from "react";

function RequireAuth({ children }: { children: ReactNode }) {
  const { session } = useAuth();
  if (!session) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route path="/" element={<OverviewPage />} />
        <Route path="/priorities" element={<PriorityQueuePage />} />
        <Route path="/alerts" element={<AlertsPage />} />
        <Route path="/campaigns" element={<CampaignHealthPage />} />
        <Route path="/keywords" element={<KeywordHealthPage />} />
        <Route path="/search-terms" element={<SearchTermsPage />} />
        <Route path="/budgets" element={<BudgetsPage />} />
        <Route path="/trends" element={<TrendsPage />} />
        <Route path="/reports" element={<ReportsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
