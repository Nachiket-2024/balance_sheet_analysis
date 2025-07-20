// --- Import React and core hooks ---
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

// --- Axios for HTTP requests ---
import axios from "axios";

export default function Dashboard() {
  const navigate = useNavigate();

  // --- Local state to store user and loading status ---
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // --- Runs once when component mounts ---
  useEffect(() => {
    const fetchUserInfo = async () => {
      // Extract token and role from URL query string
      const urlParams = new URLSearchParams(window.location.search);
      const tokenFromUrl = urlParams.get("access_token");
      const roleFromUrl = urlParams.get("role");

      // If token is in URL, save it to localStorage and clean up URL
      if (tokenFromUrl) {
        localStorage.setItem("access_token", tokenFromUrl);
        if (roleFromUrl) localStorage.setItem("role", roleFromUrl);
        window.history.replaceState({}, "", "/dashboard");
      }

      // Get token from localStorage
      const storedToken = localStorage.getItem("access_token");
      if (!storedToken) {
        navigate("/login");
        return;
      }

      try {
        // Fetch user info from backend using the token
        const response = await axios.get("http://localhost:8000/auth/me", {
          headers: {
            Authorization: `Bearer ${storedToken}`,
          },
        });

        setUser(response.data); // Store user info (including role)
      } catch (err) {
        console.error("Token error:", err);
        localStorage.removeItem("access_token");
        navigate("/login");
      } finally {
        setLoading(false);
      }
    };

    fetchUserInfo();
  }, [navigate]);

  // --- Logout handler ---
  const handleLogout = async () => {
    const token = localStorage.getItem("access_token");

    if (token) {
      try {
        await axios.post("http://localhost:8000/auth/logout", {}, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        // Clear token and redirect to login
        localStorage.removeItem("access_token");
        localStorage.removeItem("role");
        setUser(null);
        navigate("/login?logged_out=true", { replace: true });
      } catch (err) {
        console.error("Logout failed:", err);
      }
    }
  };

  // --- Show loading spinner while fetching user info ---
  if (loading) return <p>Loading user info...</p>;

  // --- Dashboard UI ---
  return (
    <div className="p-4">
      <h1 className="text-2xl font-bold mb-2">Welcome to the Balance Sheet Dashboard!</h1>
      <p>You are successfully logged in for Balance Sheet analysis.</p>

      <div className="mt-4 space-y-1">
        <p>👤 <strong>{user.name}</strong></p>
        <p>📧 {user.email}</p>
        <p>🛡️ <strong>Role:</strong> {user.role}</p>
      </div>

      {/* Logout button */}
      <button
        onClick={handleLogout}
        className="mt-6 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
      >
        Logout
      </button>

      {/* Navigation buttons */}
      <div className="mt-6 space-x-4">
        <button
          onClick={() => navigate("/balance-sheet")}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          View Balance Sheets
        </button>
      </div>
    </div>
  );
}
