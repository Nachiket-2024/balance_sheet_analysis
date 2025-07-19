import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

function LoginPage() {
  const location = useLocation();
  const navigate = useNavigate();

  const wasLoggedOut = new URLSearchParams(location.search).get("logged_out") === "true";

  const handleLogin = () => {
    // Redirect the user to the backend Google login route
    window.location.href = "http://localhost:8000/auth/login";  // Adjust with your backend login endpoint
  };

  return (
    <div style={{ textAlign: "center", marginTop: "50px" }}>
      <h1>Login to Balance Sheet Analysis App</h1>

      {/* Show success message after logout */}
      {wasLoggedOut && (
        <p style={{ color: "green" }}>
          You have been logged out successfully.
        </p>
      )}

      {/* Login Button → Redirect to backend auth route */}
      <button
        onClick={handleLogin}
        style={{
          padding: "10px 20px",
          backgroundColor: "blue",
          color: "white",
          border: "none",
          borderRadius: "5px",
          cursor: "pointer",
        }}
      >
        Login with Google
      </button>
    </div>
  );
}

export default LoginPage;
