"use client";

/**
 * Loading spinner component with pulse animation.
 */

interface LoadingSpinnerProps {
  size?: "sm" | "md" | "lg";
  message?: string;
}

const sizeClasses = {
  sm: "h-5 w-5",
  md: "h-8 w-8",
  lg: "h-12 w-12",
};

export default function LoadingSpinner({
  size = "md",
  message,
}: LoadingSpinnerProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3">
      <div
        className={`${sizeClasses[size]} animate-spin rounded-full border-2 border-slate-600 border-t-cyan-400`}
      />
      {message && (
        <p className="text-sm text-slate-400 animate-pulse">{message}</p>
      )}
    </div>
  );
}
