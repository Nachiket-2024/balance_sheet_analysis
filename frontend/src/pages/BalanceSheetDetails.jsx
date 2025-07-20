// --- Import React and hooks ---
import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";  // To get ticker/year from URL
import axios from "axios";                     // For HTTP requests

// --- Component to show details of one balance sheet ---
export default function BalanceSheetDetails() {
    const { ticker, year } = useParams();       // Extract URL params
    const [sheet, setSheet] = useState(null);   // Store fetched balance sheet data
    const [loading, setLoading] = useState(true); // Loading spinner state

    // --- Fetch balance sheet details when ticker or year changes ---
    useEffect(() => {
        setLoading(true);
        axios
            .get(`http://localhost:8000/balance-sheet/${ticker}/${year}`)  // Full backend URL
            .then((res) => {
                setSheet(res.data);            // Save response JSON
                setLoading(false);             // Stop loading
            })
            .catch(() => {
                setSheet(null);                // Clear sheet if error
                setLoading(false);             // Stop loading spinner
            });
    }, [ticker, year]);

    // --- Render loading message ---
    if (loading) return <p className="p-4">Loading...</p>;

    // --- Render error message if no data ---
    if (!sheet) return <p className="p-4">Balance sheet not found.</p>;

    // --- Render table of all fields in the balance sheet ---
    return (
        <div className="p-6 max-w-5xl mx-auto">
            <h1 className="text-2xl font-bold mb-4">
                Balance Sheet – {ticker.toUpperCase()} ({year})
            </h1>
            <table className="w-full text-sm border">
                <tbody>
                    {/* Display each key-value pair in sheet, format keys nicely */}
                    {Object.entries(sheet).map(([key, value]) => (
                        <tr key={key} className="border-b">
                            <td className="font-medium px-4 py-2 capitalize">{key.replaceAll("_", " ")}</td>
                            <td className="px-4 py-2">{value ?? "-"}</td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}
