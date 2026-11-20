import { useQueryClient } from "@tanstack/react-query";
import { useEffect, type ReactNode } from "react";
import { Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { setupInterceptors } from "./api/client";
import { useAuth } from "./auth/AuthContext";
import Layout from "./components/Layout";
import AdminCasesPage from "./pages/AdminCasesPage";
import AttemptPage from "./pages/AttemptPage";
import CaseEditorPage from "./pages/CaseEditorPage";
import CatalogPage from "./pages/CatalogPage";
import ChatLogsPage from "./pages/ChatLogsPage";
import ChatPage from "./pages/ChatPage";
import HistoryPage from "./pages/HistoryPage";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import TextbooksPage from "./pages/TextbooksPage";

function RequireAuth({ roles, children }: { roles?: string[]; children: ReactNode }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (roles && !roles.includes(user.role)) return <Navigate to="/" replace />;
  return <Layout>{children}</Layout>;
}

const STAFF = ["teacher", "admin"];

export default function App() {
  const navigate = useNavigate();
  const { loading, logout } = useAuth();
  const queryClient = useQueryClient();

  useEffect(
    () =>
      setupInterceptors(navigate, () => {
        logout();
        queryClient.clear();
      }),
    // Register once. `navigate` changes identity on every route change in react-router v7;
    // re-registering on each change is pointless and it always navigates to an absolute path anyway.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  if (loading) return null;

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/" element={<RequireAuth><CatalogPage /></RequireAuth>} />
      <Route path="/attempt/:id" element={<RequireAuth><AttemptPage /></RequireAuth>} />
      <Route path="/history" element={<RequireAuth><HistoryPage /></RequireAuth>} />
      <Route path="/chat" element={<RequireAuth><ChatPage /></RequireAuth>} />
      <Route path="/admin/cases" element={<RequireAuth roles={STAFF}><AdminCasesPage /></RequireAuth>} />
      <Route path="/admin/cases/:id" element={<RequireAuth roles={STAFF}><CaseEditorPage /></RequireAuth>} />
      <Route path="/admin/chat-logs" element={<RequireAuth roles={STAFF}><ChatLogsPage /></RequireAuth>} />
      <Route path="/admin/textbooks" element={<RequireAuth><TextbooksPage /></RequireAuth>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
