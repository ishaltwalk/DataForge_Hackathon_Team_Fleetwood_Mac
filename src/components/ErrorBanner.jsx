
export default function ErrorBanner({ message, onRetry }) {
  if (!message) return null;

  return (
    <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg flex items-center justify-between text-sm text-red-800">
      <span>{message}</span>
      {onRetry && (
        <button
          onClick={onRetry}
          className="text-xs underline font-medium hover:text-red-950 cursor-pointer"
        >
          Try again
        </button>
      )}
    </div>
  );
}