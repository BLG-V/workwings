import { Routes, Route } from "react-router-dom";
import { Layout } from "@/components/Layout";
import { RequireAuth } from "@/components/RequireAuth";
import HomeChatPage from "@/pages/HomeChatPage/HomeChatPage";
import StudioPage from "@/pages/StudioPage/StudioPage";
import ProjectsPage from "@/pages/ProjectsPage/ProjectsPage";
import WorkflowEditorPage from "@/pages/WorkflowEditorPage/WorkflowEditorPage";
import AgentMarketPage from "@/pages/AgentMarketPage/AgentMarketPage";
import RunsPage from "@/pages/RunsPage/RunsPage";
import SettingsPage from "@/pages/SettingsPage/SettingsPage";
import HistoryPage from "@/pages/HistoryPage/HistoryPage";
import LoginPage from "@/pages/LoginPage/LoginPage";
import RegisterPage from "@/pages/RegisterPage/RegisterPage";
import LegalPage from "@/pages/LegalPage/LegalPage";
import LandingPage from "@/pages/LandingPage/LandingPage";
import AdvancedProjectPage from "@/pages/AdvancedProjectPage/AdvancedProjectPage";
import AdminPage from "@/pages/AdminPage/AdminPage";
import NotFoundPage from "@/pages/NotFoundPage/NotFoundPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/terms" element={<LegalPage />} />
      <Route path="/privacy" element={<LegalPage />} />

      {/* 全部业务页需登录：对话/历史等按 userId 本机分桶 */}
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route path="chat" element={<HomeChatPage />} />
        <Route path="studio" element={<StudioPage />} />
        <Route path="studio/:kind" element={<StudioPage />} />
        <Route path="advanced" element={<AdvancedProjectPage />} />
        <Route path="projects" element={<ProjectsPage />} />
        <Route path="workflow/:projectId" element={<WorkflowEditorPage />} />
        <Route path="agents" element={<AgentMarketPage />} />
        <Route path="runs" element={<RunsPage />} />
        <Route path="history" element={<HistoryPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="admin" element={<AdminPage />} />
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
