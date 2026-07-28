import { Suspense, lazy } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import LoginPage from "./auth/LoginPage";
import { ErrorBoundary } from "./components/ErrorBoundary";
import Layout from "./components/Layout";
import { Spinner } from "./components/ui";
import type { ReactNode } from "react";

// Pages are code-split so the initial bundle only carries the shell + the first
// route the user lands on; the rest load on navigation.
const OverviewPage = lazy(() => import("./pages/OverviewPage"));
const CampaignExplorerPage = lazy(() => import("./pages/CampaignExplorerPage"));
const PriorityQueuePage = lazy(() => import("./pages/PriorityQueuePage"));
const AlertsPage = lazy(() => import("./pages/AlertsPage"));
const CampaignHealthPage = lazy(() => import("./pages/CampaignHealthPage"));
const KeywordHealthPage = lazy(() => import("./pages/KeywordHealthPage"));
const SearchTermsPage = lazy(() => import("./pages/SearchTermsPage"));
const BudgetsPage = lazy(() => import("./pages/BudgetsPage"));
const TrendsPage = lazy(() => import("./pages/TrendsPage"));
const ReportsPage = lazy(() => import("./pages/ReportsPage"));

function RequireAuth({ children }: { children: ReactNode }) {
  const { session } = useAuth();
  if (!session) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <ErrorBoundary>
      <Suspense fallback={<Spinner label="Loading…" />}>
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
            <Route path="/explorer" element={<CampaignExplorerPage />} />
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
      </Suspense>
    </ErrorBoundary>
  );
}
