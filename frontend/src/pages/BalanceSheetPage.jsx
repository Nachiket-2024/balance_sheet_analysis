// --- Import core libraries ---
import React, { useEffect, useState } from "react";          // React hooks for lifecycle and state
import axios from "axios";                                   // For HTTP requests
import { useNavigate } from "react-router-dom";              // Navigation between routes

// --- Balance Sheet Page Component ---
export default function BalanceSheetPage() {
    // --- Local State ---
    const [companies, setCompanies] = useState([]);          // Companies + their balance sheets
    const [loading, setLoading] = useState(true);            // Spinner for loading
    const [error, setError] = useState(null);                // Track API errors
    const [form, setForm] = useState({                       // Form to create balance sheet
        ticker: "",
        year: "",
    });
    const navigate = useNavigate();                          // Redirect user

    // --- Fetch data when component mounts ---
    useEffect(() => {
        fetchBalanceSheets();                                // Load companies on mount
    }, []);

    // --- API Call: Fetch all companies + balance sheets ---
    const fetchBalanceSheets = async () => {
        try {
            const token = localStorage.getItem("access_token");
            const res = await axios.get("http://localhost:8000/balance-sheet/companies", {  // Full URL to backend
                headers: {
                    Authorization: `Bearer ${token}`,           // Send auth token
                },
            });
            setCompanies(res.data);                            // Set company data from response
            setError(null);                                    // Clear previous errors
        } catch (err) {
            // If 404, treat as no companies instead of error
            if (err.response?.status === 404) {
                setCompanies([]);                              // No companies yet
                setError(null);                                // No error to show
            } else {
                setError("Could not fetch balance sheets.");  // Show error message
            }
        } finally {
            setLoading(false);                                 // Stop loading spinner
        }
    };

    // --- Update form state on user input ---
    const handleChange = (e) => {
        setForm({ ...form, [e.target.name]: e.target.value }); // Update ticker/year form fields
    };

    // --- API Call: Create balance sheet using ticker/year only ---
    const handleCreate = async () => {
        try {
            const token = localStorage.getItem("access_token");
            await axios.post(
                `http://localhost:8000/balance-sheet/${form.ticker}/${form.year}`, // Use full backend URL
                {},  // No request body payload needed
                {
                    headers: {
                        Authorization: `Bearer ${token}`,       // Auth header
                    },
                }
            );
            await fetchBalanceSheets();                        // Refresh data after creation
            alert("Balance sheet created successfully.");
            setForm({ ticker: "", year: "" });                 // Reset form fields
        } catch (err) {
            alert("Error creating balance sheet.");            // Error alert on failure
        }
    };

    // --- API Call: Delete balance sheet ---
    const handleDelete = async (ticker, year) => {
        try {
            const token = localStorage.getItem("access_token");
            await axios.delete(`http://localhost:8000/balance-sheet/${ticker}/${year}`, {
                headers: {
                    Authorization: `Bearer ${token}`,           // Auth header
                },
            });
            await fetchBalanceSheets();                        // Refresh after deletion
            alert("Deleted successfully.");
        } catch (err) {
            alert("Error deleting balance sheet.");            // Error alert
        }
    };

    // --- Show loading spinner while fetching data ---
    if (loading) return <div className="text-center mt-10">Loading...</div>;

    return (
        <div className="p-8">
            {/* Page Title */}
            <h1 className="text-3xl font-bold mb-6">Balance Sheets Overview</h1>

            {/* Back Button */}
            <button
                onClick={() => navigate("/dashboard")}
                className="mb-6 px-4 py-2 bg-gray-200 rounded hover:bg-gray-300 transition"
            >
                ← Back to Dashboard
            </button>

            {/* Error Display */}
            {error && <div className="text-red-500 mb-4">{error}</div>}

            {/* Form Section */}
            <div className="mb-10 border p-4 rounded bg-gray-50">
                <h2 className="text-xl font-semibold mb-4">Add New Balance Sheet</h2>

                {/* Input Form Grid */}
                <div className="grid grid-cols-2 gap-4 mb-4">
                    <input
                        name="ticker"
                        value={form.ticker}
                        onChange={handleChange}
                        placeholder="Ticker"
                        className="border p-2 rounded"
                    />
                    <input
                        name="year"
                        value={form.year}
                        onChange={handleChange}
                        placeholder="Year"
                        className="border p-2 rounded"
                    />
                </div>

                {/* Submit Button */}
                <button
                    onClick={handleCreate}
                    className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
                >
                    Create
                </button>

                {/* Note */}
                <p className="text-sm text-gray-500 italic mt-2">
                    The balance sheet data will be automatically fetched using yfinance.
                </p>
            </div>

            {/* No companies message */}
            {companies.length === 0 && (
                <p className="text-center text-gray-500 italic">
                    No companies or balance sheet data available.
                </p>
            )}

            {/* Companies + Balance Sheets Table */}
            {companies.map(({ company, balance_sheets }) => (
                <div key={company.name} className="mb-10 border p-4 rounded-md shadow">
                    <h2 className="text-xl font-semibold mb-2">
                        {company.name}
                    </h2>

                    {balance_sheets.length > 0 ? (
                        <table className="w-full border text-sm">
                            <thead className="bg-gray-100">
                                <tr>
                                    <th className="border px-3 py-1">Year</th>
                                    <th className="border px-3 py-1">Assets</th>
                                    <th className="border px-3 py-1">Liabilities</th>
                                    <th className="border px-3 py-1">Equity</th>
                                    <th className="border px-3 py-1">Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {balance_sheets.map((sheet) => (
                                    <tr key={`${sheet.ticker}-${sheet.year}`}>
                                        <td className="border px-3 py-1">{sheet.year}</td>
                                        {/* Use values from schema, provide fallback '-' */}
                                        <td className="border px-3 py-1">{sheet.total_assets ?? "-"}</td>
                                        <td className="border px-3 py-1">{sheet.total_liabilities_net_minority_interest ?? "-"}</td>
                                        <td className="border px-3 py-1">{sheet.stockholders_equity ?? "-"}</td>
                                        <td className="border px-3 py-1 space-x-2">
                                            <a
                                                href={`/balance-sheet/${sheet.ticker}/${sheet.year}`}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="text-blue-600 underline"
                                            >
                                                View Full
                                            </a>
                                            <button
                                                className="text-red-600 underline"
                                                onClick={() => handleDelete(sheet.ticker, sheet.year)}
                                            >
                                                Delete
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    ) : (
                        <p className="text-gray-500 italic mt-2">No balance sheets available.</p>
                    )}
                </div>
            ))}
        </div>
    );
}
