// Import core React runtime and rendering logic
import React from "react";
import ReactDOM from "react-dom/client";

// React Router components for routing and navigation
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
} from "react-router-dom";

// Custom components
import ProtectedRoute from "./components/ProtectedRoute"; // Guards private routes
import Layout from "./components/Layout";                 // Shared layout with nav + meta
import LoginPage from "./pages/LoginPage";                // Public login screen
import Dashboard from "./pages/DashboardPage";            // Main user dashboard

// Mount the root app
ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode> {/* Helps detect potential problems in development */}
    <Router>
      <Routes>
        {/* Public route for login */}
        <Route path="/login" element={<LoginPage />} />

        {/* PUBLIC Dashboard route — it handles its own token logic */}
        <Route path="/dashboard" element={<Dashboard />} />

        {/* Layout with nested protected routes */}
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          {/* Redirect base / to dashboard */}
          <Route index element={<Navigate to="/dashboard" replace />} />

          {/* Example nested routes under layout */}
          {/* These should be protected */}
          {/* <Route path="companies" element={<CompaniesPage />} />
          <Route path="financials" element={<FinancialsPage />} /> */}
        </Route>
      </Routes>
    </Router>
  </React.StrictMode>
);
