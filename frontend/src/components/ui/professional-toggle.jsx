import React from "react";
import { cn } from "@/lib/utils";

const ProfessionalToggle = React.forwardRef(({ 
  className, 
  checked, 
  onCheckedChange, 
  disabled,
  leftLabel = "OFF",
  rightLabel = "ON",
  leftColor = "bg-gray-600",
  rightColor = "bg-green-500",
  size = "default",
  ...props 
}, ref) => {
  const sizeClasses = {
    sm: "h-6 w-12",
    default: "h-8 w-16", 
    lg: "h-10 w-20"
  };
  
  const dotSizeClasses = {
    sm: "h-4 w-4",
    default: "h-6 w-6",
    lg: "h-8 w-8"
  };

  const translateClasses = {
    sm: checked ? "translate-x-6" : "translate-x-1",
    default: checked ? "translate-x-8" : "translate-x-1", 
    lg: checked ? "translate-x-10" : "translate-x-1"
  };

  const textSizeClasses = {
    sm: "text-[8px]",
    default: "text-[10px]",
    lg: "text-xs"
  };

  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onCheckedChange?.(!checked)}
      className={cn(
        "relative inline-flex items-center rounded-full border-2 border-transparent transition-all duration-300 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:ring-offset-2 focus:ring-offset-gray-900 disabled:cursor-not-allowed disabled:opacity-50",
        sizeClasses[size],
        checked ? rightColor : leftColor,
        "shadow-inner",
        className
      )}
      ref={ref}
      {...props}
    >
      {/* Background Labels */}
      <div className="absolute inset-0 flex items-center justify-between px-2">
        <span className={cn(
          "font-bold text-white transition-opacity duration-300",
          textSizeClasses[size],
          !checked ? "opacity-100" : "opacity-40"
        )}>
          {leftLabel}
        </span>
        <span className={cn(
          "font-bold text-white transition-opacity duration-300", 
          textSizeClasses[size],
          checked ? "opacity-100" : "opacity-40"
        )}>
          {rightLabel}
        </span>
      </div>
      
      {/* Sliding Dot */}
      <div
        className={cn(
          "absolute top-1 rounded-full bg-white shadow-lg ring-0 transition-transform duration-300 ease-in-out",
          dotSizeClasses[size],
          translateClasses[size],
          "shadow-xl"
        )}
        style={{
          boxShadow: checked 
            ? "0 4px 12px rgba(34, 197, 94, 0.4)" 
            : "0 4px 12px rgba(0, 0, 0, 0.3)"
        }}
      />
    </button>
  );
});

ProfessionalToggle.displayName = "ProfessionalToggle";

export { ProfessionalToggle };