import { useLocation } from "react-router-dom";  // Hook for accessing URL query params

// Login screen shown at /login
function LoginPage() {
  const location = useLocation();  // Grab current location object from React Router

  // Check if redirected here after logout
  const wasLoggedOut = new URLSearchParams(location.search).get("logged_out") === "true";

  // Trigger backend login redirect to Google
  const handleLogin = () => {
    window.location.replace("http://localhost:8000/auth/login");  // FastAPI → Google OAuth flow
  };

  return (
    <div className="flex flex-col items-center justify-center h-screen bg-gray-100">
      <h1 className="text-3xl font-bold mb-6">Login to Doctor Agentic App</h1>

      {/* Show success message after logout */}
      {wasLoggedOut && (
        <p className="mb-4 text-green-700 font-semibold">
          You have been logged out successfully.
        </p>
      )}

      {/* Login Button → Redirects to Google */}
      <button
        onClick={handleLogin}
        className="bg-blue-600 text-white px-6 py-3 rounded-lg shadow-md hover:bg-blue-700 transition"
      >
        Login with Google
      </button>
    </div>
  );
}

export default LoginPage;  // Export for use in router
