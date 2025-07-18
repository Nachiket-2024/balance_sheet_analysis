import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";

// Component to protect routes that require authentication
export default function ProtectedRoute({ children }) {
  const navigate = useNavigate(); // React Router navigation hook
  const [checkingAuth, setCheckingAuth] = useState(true); // Track if auth check is in progress

  useEffect(() => {
    // On mount: check auth status by calling /auth/me
    axios
      .get("http://localhost:8000/auth/me", { withCredentials: true }) // Send cookies with request
      .then(() => {
        setCheckingAuth(false); // User is authenticated
      })
      .catch(() => {
        navigate("/login", { replace: true }); // Not authenticated → redirect to login
      });
  }, [navigate]);

  // While auth check is in progress, show temporary message
  if (checkingAuth) {
    return <p>Checking authentication...</p>;
  }

  // If authenticated, render the protected children (nested routes or components)
  return children;
}
