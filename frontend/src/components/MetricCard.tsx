import React from "react";

interface MetricCardProps {
  label: string;
  value: string | number;
  subtext?: string;
  variant?: "cyan" | "emerald" | "amber" | "indigo";
  icon?: React.ReactNode;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  label,
  value,
  subtext,
  variant = "cyan",
  icon,
}) => {
  return (
    <div className={`glass-card kpi-card ${variant}`}>
      <div className="kpi-label">
        <span>{label}</span>
        {icon && <span>{icon}</span>}
      </div>
      <div className="kpi-value">{value}</div>
      {subtext && <div className="kpi-subtext">{subtext}</div>}
    </div>
  );
};
