import { Outlet } from "react-router-dom";   // Renders the matched child route's component inside layout
import TopNavBar from "./TopNavBar";         // Global top navigation bar
import MetaBar from "./MetaBar";             // Contextual meta bar below the nav (e.g., page title, filters)

export default function Layout() {
  return (
    <div className="min-h-screen bg-gray-50">
      {/* 
        --- Fixed Top Navigation Bar ---
        - Always stays at top (z-50 ensures highest stacking)
        - White background and subtle shadow
      */}
      <header className="fixed top-0 left-0 w-full z-50 bg-white shadow-md">
        <TopNavBar />
      </header>

      {/* 
        --- Fixed MetaBar ---
        - Positioned right below the TopNavBar (top-14 = 3.5rem assuming navbar is 14)
        - Lower z-index than navbar to layer correctly
        - Can show breadcrumb, context info, filters, etc.
      */}
      <div className="fixed top-14 left-0 w-full z-40 bg-blue-100 border-b border-blue-300">
        <MetaBar />
      </div>

      {/* 
        --- Scrollable Main Area ---
        - Padding top = height of TopNavBar + MetaBar (14 + 14 = 28 => pt-28)
        - Horizontal padding (px-4) and bottom spacing (pb-10) for breathing room
        - <Outlet /> renders nested route components here
      */}
      <main className="pt-28 px-4 pb-10">
        <Outlet />
      </main>
    </div>
  );
}
