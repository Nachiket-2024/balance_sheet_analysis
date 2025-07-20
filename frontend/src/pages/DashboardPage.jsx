import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";

export default function Dashboard() {
  const navigate = useNavigate();

  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // State for LLM interaction
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [llmLoading, setLlmLoading] = useState(false);
  const [llmError, setLlmError] = useState(null);

  // Runs once when component mounts
  useEffect(() => {
    const fetchUserInfo = async () => {
      const urlParams = new URLSearchParams(window.location.search);
      const tokenFromUrl = urlParams.get("access_token");
      const roleFromUrl = urlParams.get("role");

      if (tokenFromUrl) {
        localStorage.setItem("access_token", tokenFromUrl);
        if (roleFromUrl) localStorage.setItem("role", roleFromUrl);
        window.history.replaceState({}, "", "/dashboard");
      }

      const storedToken = localStorage.getItem("access_token");
      if (!storedToken) {
        navigate("/login");
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

        localStorage.removeItem("access_token");
        localStorage.removeItem("role");
        setUser(null);
        navigate("/login?logged_out=true", { replace: true });
      } catch (err) {
        console.error("Logout failed:", err);
      }
    }
  };

  // --- Handle question submission to LLM ---
  const handleQuestionSubmit = async () => {
    setLlmLoading(true);
    setLlmError(null);

    try {
      const token = localStorage.getItem("access_token");
      if (!token) {
        navigate("/login");
        return;
      }

      const response = await axios.post(
        "http://localhost:8000/llm/chat",
        {
          question, // Send only the question to the backend
        },
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      setAnswer(response.data.answer);  // Set LLM's answer to state
    } catch (err) {
      console.error("Error fetching LLM response:", err);
      setLlmError("Failed to fetch answer from LLM.");
    } finally {
      setLlmLoading(false);
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

      {/* LLM Chat Interface */}
      <div className="mt-8">
        <h2 className="text-xl font-semibold">Ask LLM about Balance Sheets</h2>
        <div className="mt-4">
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask a question about the balance sheet..."
            rows={4}
            className="w-full p-2 border rounded-md"
          />
        </div>

        <button
          onClick={handleQuestionSubmit}
          disabled={llmLoading || !question}
          className={`mt-2 px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 ${llmLoading || !question ? "opacity-50 cursor-not-allowed" : ""}`}
        >
          {llmLoading ? "Loading..." : "Ask LLM"}
        </button>

        {llmError && (
          <div className="mt-4 text-red-600">{llmError}</div>
        )}

        {answer && (
          <div className="mt-4 p-4 border border-gray-300 rounded-md">
            <h3 className="font-semibold">LLM Answer:</h3>
            <p>{answer}</p>
          </div>
        )}
      </div>
    </div>
  );
}
