import { Link } from "react-router-dom";  // 🔗 Import React Router's Link for client-side navigation

// 🏢 Top navigation bar for balance sheet and financial management
export default function TopNavBar() {
  return (
    // 🔲 Outer nav container with padding and horizontal alignment
    <nav className="flex items-center justify-between px-6 py-3">
      {/* 🎨 Brand title on the left */}
      <h1 className="text-xl font-semibold text-blue-700">
        Balance Sheet Analysis
      </h1>

      {/* 🔗 Navigation links on the right, spaced evenly */}
      <div className="space-x-6 text-blue-600 font-medium">
        {/* 📊 Link to the companies overview page */}
        <Link to="/companies">Companies</Link>

        {/* 💵 Link to the financial indicators analysis page */}
        <Link to="/financials">Financials</Link>

        {/* 📅 Link to the balance sheet history page */}
        <Link to="/history">History</Link>
      </div>
    </nav>
  );
}
