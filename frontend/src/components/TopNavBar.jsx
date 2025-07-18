import { Link } from "react-router-dom";  // 🔗 Import React Router's Link for client-side navigation

// 🩺 Top navigation bar for branding and quick links
export default function TopNavBar() {
  return (
    // 🔲 Outer nav container with padding and horizontal alignment
    <nav className="flex items-center justify-between px-6 py-3">
      {/* 🎨 Brand title on the left */}
      <h1 className="text-xl font-semibold text-blue-700">
        Doctor Appointment System
      </h1>

      {/* 🔗 Navigation links on the right, spaced evenly */}
      <div className="space-x-6 text-blue-600 font-medium">
        {/* 🩺 Link to the appointments management page */}
        <Link to="/appointments">Appointments</Link>

        {/* 👨‍⚕️ Link to the doctor management page */}
        <Link to="/doctors">Doctors</Link>

        {/* 🧑‍⚕️ Link to the patient management page */}
        <Link to="/patients">Patients</Link>
      </div>
    </nav>
  );
}
