export default function MetaBar() {
  return (
    <div className="flex items-center justify-between px-6 py-2">
      {/* 
        Outer wrapper with:
        - `flex` to arrange content horizontally
        - `items-center` vertically centers all text/inputs
        - `justify-between` spaces items left and right (but since only left side is used now, acts like `flex-start`)
        - `px-6 py-2` adds horizontal and vertical padding
      */}

      <div className="text-sm font-medium">
        {/* 
          Inner container with:
          - `text-sm` for compact appearance
          - `font-medium` for slight emphasis on text
        */}

        {/* Appointment Status */}
        <span className="mr-4">
          🩺 Appointment Status: <strong>Scheduled</strong>
        </span>

        {/* Patient Name */}
        <span className="mr-4">
          🧑‍⚕️ Patient:{" "}
          <input
            className="px-2 py-1 border rounded"
            defaultValue="John Doe"  // Update this with actual patient name
          />
        </span>

        {/* Doctor Name */}
        <span className="mr-4">
          👨‍⚕️ Doctor:{" "}
          <input
            className="px-2 py-1 border rounded"
            defaultValue="Dr. Smith"  // Update this with actual doctor name
          />
        </span>

        {/* Appointment Date and Time */}
        <span>
          📅 Appointment Time:{" "}
          <input
            className="px-2 py-1 border rounded w-32"
            defaultValue="2025-07-20 10:00 AM"  // Update with actual appointment date
          />
        </span>
      </div>
    </div>
  );
}
