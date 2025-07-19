import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom"; // React Router hook to navigate
import axios from "axios";

export default function Dashboard() {
  const navigate = useNavigate(); // For redirecting the user
  const [user, setUser] = useState(null); // Holds current user info
  const [loading, setLoading] = useState(true); // Tracks loading state for user info

  useEffect(() => {
    // Fetch user info from /auth/me endpoint
    const fetchUserInfo = async () => {
      const token = localStorage.getItem("access_token"); // Get JWT token from localStorage

      if (!token) {
        // If no token exists, navigate to login page
        navigate("/login");
        return;
      }

      try {
        const response = await axios.get("http://localhost:8000/auth/me", {
          headers: {
            Authorization: `Bearer ${token}`, // Send the token in the Authorization header
          },
        });
        setUser(response.data); // Store user info in state
      } catch (err) {
        setUser(null); // Nullify user if any error occurs
      } finally {
        setLoading(false); // End loading state
      }
    };

    fetchUserInfo();
  }, [navigate]);

  const handleLogout = async () => {
    const token = localStorage.getItem("access_token");

    if (token) {
      try {
        await axios.post(
          "http://localhost:8000/auth/logout", // Call logout API
          {},
          {
            headers: {
              Authorization: `Bearer ${token}`, // Send token for logout
            },
          }
        );
        localStorage.removeItem("access_token"); // Remove token from localStorage on logout
        setUser(null); // Clear user info from state
        navigate("/login?logged_out=true", { replace: true }); // Redirect to login page
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

      {/* User details */}
      <p className="mt-4">👤 <strong>{user.name}</strong></p>
      <p>{user.email}</p>

      {/* Logout button */}
      <button
        onClick={handleLogout}
        className="mt-6 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
      >
        Logout
      </button>

      {/* Button to navigate to Companies analysis page */}
      <button
        onClick={() => navigate("/companies")} // Navigate to Companies page
        className="mt-6 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
      >
        Manage Companies
      </button>

      {/* Button to navigate to Financial indicators page */}
      <button
        onClick={() => navigate("/financials")} // Navigate to Financial indicators page
        className="mt-6 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
      >
        Financial Analysis
      </button>

      {/* Button to navigate to Balance Sheet History page */}
      <button
        onClick={() => navigate("/history")} // Navigate to Balance Sheet history page
        className="mt-6 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
      >
        Balance Sheet History
      </button>
    </div>
  );
}
