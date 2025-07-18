import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";         // React Router hook to navigate
import axios from "axios";

export default function Dashboard() {
  const navigate = useNavigate();                       // For redirecting the user
  const [user, setUser] = useState(null);               // Holds current user info
  const [loading, setLoading] = useState(true);         // Tracks loading state for user info

  useEffect(() => {
    axios.get("http://localhost:8000/auth/me", { withCredentials: true })
      .then((res) => {
        setUser(res.data);                              // Store user info in state
        setLoading(false);
      })
      .catch((err) => {
        setUser(null);                                  // Nullify user on error
        setLoading(false);
      });
  }, []);

  const handleLogout = () => {
    axios.post("http://localhost:8000/auth/logout", {}, { withCredentials: true })
      .then(() => {
        setUser(null);
        navigate("/login?logged_out=true", { replace: true });  // Redirect to login
      })
      .catch((err) => {
        console.error("Logout failed:", err);
      });
  };

  if (loading) return <p>Loading user info...</p>;

  return (
    <div className="p-4">
      <h1 className="text-2xl font-bold mb-2">Welcome to your Dashboard!</h1>
      <p>You are successfully logged in via Google OAuth.</p>

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

      {/* Button to navigate to Doctors page */}
      <button
        onClick={() => navigate("/doctors")} // Navigate to the Doctors management page
        className="mt-6 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
      >
        Manage Doctors
      </button>

      {/* Button to navigate to Patients page */}
      <button
        onClick={() => navigate("/patients")} // Navigate to the Patients management page
        className="mt-6 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
      >
        Manage Patients
      </button>

      {/* Button to navigate to Appointments page */}
      <button
        onClick={() => navigate("/appointments")} // Navigate to the Appointments management page
        className="mt-6 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
      >
        Manage Appointments
      </button>
    </div>
  );
}
