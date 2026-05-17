import { Route, Routes } from "react-router-dom";

import { Layout } from "./components/Layout";
import { AuthProvider, RequireAuth } from "./lib/auth";
import { Admin } from "./pages/Admin";
import { AgentDetail } from "./pages/AgentDetail";
import { Dashboard } from "./pages/Dashboard";
import { Landing } from "./pages/Landing";
import { RentAgent } from "./pages/RentAgent";

export function App() {
  return (
    <AuthProvider>
      <Layout>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route
            path="/rent"
            element={
              <RequireAuth>
                <RentAgent />
              </RequireAuth>
            }
          />
          <Route
            path="/dashboard"
            element={
              <RequireAuth>
                <Dashboard />
              </RequireAuth>
            }
          />
          <Route
            path="/agents/:id"
            element={
              <RequireAuth>
                <AgentDetail />
              </RequireAuth>
            }
          />
          <Route
            path="/admin"
            element={
              <RequireAuth admin>
                <Admin />
              </RequireAuth>
            }
          />
          <Route path="*" element={<Landing />} />
        </Routes>
      </Layout>
    </AuthProvider>
  );
}
