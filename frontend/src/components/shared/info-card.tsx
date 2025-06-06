"use client";
import { Card, CardContent } from "@/components/ui/card";

interface InfoCardProps {
  title: string;
  items: string[];
  variant?: "default" | "info" | "warning" | "success";
  className?: string;
}

export function InfoCard({
  title,
  items,
  variant = "info",
  className = "",
}: InfoCardProps) {
  const getVariantClasses = (variant: string) => {
    const variants = {
      default: "bg-gray-50 border-gray-200 text-gray-900",
      info: "bg-blue-50 border-blue-200 text-blue-900",
      warning: "bg-yellow-50 border-yellow-200 text-yellow-900",
      success: "bg-green-50 border-green-200 text-green-900",
    };
    return variants[variant as keyof typeof variants] || variants.info;
  };

  const getTextColor = (variant: string) => {
    const colors = {
      default: "text-gray-800",
      info: "text-blue-800",
      warning: "text-yellow-800",
      success: "text-green-800",
    };
    return colors[variant as keyof typeof colors] || colors.info;
  };

  return (
    <Card className={`${getVariantClasses(variant)} ${className}`}>
      <CardContent className="pt-6">
        <h3 className="font-semibold mb-2">{title}</h3>
        <ul className={`text-sm space-y-1 ${getTextColor(variant)}`}>
          {items.map((item, index) => (
            <li key={index}>{item}</li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
