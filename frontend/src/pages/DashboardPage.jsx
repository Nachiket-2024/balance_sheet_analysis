import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom"; // React Router hook to navigate
import axios from "axios";

export default function Dashboard() {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchUserInfo = async () => {
      // First, try to get token from the URL
      const token = new URLSearchParams(window.location.search).get("access_token");

      if (token) {
        // Store token in localStorage to persist it across page reloads
        localStorage.setItem("access_token", token);
        navigate("/dashboard"); // Redirect to dashboard once token is stored
        return; // Early return to prevent further processing
      }

      // If token doesn't exist in URL, try to get it from localStorage
      const storedToken = localStorage.getItem("access_token");

      if (!storedToken) {
        navigate("/login"); // Redirect to login page if no token is found
        return;
      }

      try {
        const response = await axios.get("http://localhost:8000/auth/me", {
          headers: {
            Authorization: `Bearer ${storedToken}`,
          },
        });
        setUser(response.data);
      } catch (err) {
        setUser(null);
      } finally {
        setLoading(false);
      }
    };

    fetchUserInfo();
  }, [navigate]);

  const handleLogout = async () => {
    const token = localStorage.getItem("access_token");

    if (token) {
      try {
        await axios.post("http://localhost:8000/auth/logout", {}, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        localStorage.removeItem("access_token");
        setUser(null);
        navigate("/login?logged_out=true", { replace: true });
      } catch (err) {
        console.error("Logout failed:", err);
      }
    }
  };

  if (loading) return <p>Loading user info...</p>;

  return (
    <div className="p-4">
      <h1 className="text-2xl font-bold mb-2">Welcome to the Balance Sheet Dashboard!</h1>
      <p>You are successfully logged in for Balance Sheet analysis.</p>

      <p className="mt-4">👤 <strong>{user.name}</strong></p>
      <p>{user.email}</p>

      <button
        onClick={handleLogout}
        className="mt-6 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
      >
        Logout
      </button>

      <button
        onClick={() => navigate("/companies")}
        className="mt-6 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
      >
        Manage Companies
      </button>

      <button
        onClick={() => navigate("/financials")}
        className="mt-6 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
      >
        Financial Analysis
      </button>

      <button
        onClick={() => navigate("/history")}
        className="mt-6 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
      >
        Balance Sheet History
      </button>
    </div>
  );
}
