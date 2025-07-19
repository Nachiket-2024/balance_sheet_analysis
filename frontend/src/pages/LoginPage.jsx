import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

function LoginPage() {
  const navigate = useNavigate();

  useEffect(() => {
    const token = localStorage.getItem("access_token");

    if (token) {
      // If the token is already in localStorage, redirect directly to the dashboard
      navigate("/dashboard");
    }
  }, [navigate]);

  const handleLogin = () => {
    // Redirect the user to the backend Google login route
    window.location.href = "http://localhost:8000/auth/login";  // Adjust with your backend login endpoint
  };

  return (
    <div style={{ textAlign: "center", marginTop: "50px" }}>
      <h1>Login to Balance Sheet Analysis App</h1>

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
