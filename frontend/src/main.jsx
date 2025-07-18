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

        {/* Protected route for authenticated areas (with nested routes inside Layout) */}
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          {/* Default redirect from `/` to `/dashboard` */}
          <Route index element={<Navigate to="/dashboard" replace />} />

          {/* Actual dashboard page */}
          <Route path="dashboard" element={<Dashboard />} />

        </Route>
      </Routes>
    </Router>
  </React.StrictMode>
);
