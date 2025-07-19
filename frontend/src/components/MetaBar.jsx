export default function MetaBar() {
  return (
    <div className="flex items-center justify-between px-6 py-2">
      {/* Outer wrapper with flex properties */}

      <div className="text-sm font-medium">
        {/* Inner container with compact text */}

        {/* Company Information */}
        <span className="mr-4">
          🏢 Company: <strong>ABC Corp</strong>
        </span>

        {/* Ticker Symbol */}
        <span className="mr-4">
          📊 Ticker: <strong>ABC</strong>
        </span>

        {/* Financial Year */}
        <span className="mr-4">
          📅 Fiscal Year: <strong>2024</strong>
        </span>

        {/* Revenue */}
        <span className="mr-4">
          💵 Revenue: <strong>$1,500,000</strong>
        </span>

        {/* Net Income */}
        <span className="mr-4">
          💰 Net Income: <strong>$300,000</strong>
        </span>

        {/* Total Assets */}
        <span>
          🏦 Total Assets: <strong>$5,000,000</strong>
        </span>
      </div>
    </div>
  );
}
