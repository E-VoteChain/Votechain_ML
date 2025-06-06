"use client";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface StatusItem {
  label: string;
  completed: boolean;
}

interface VerificationStatusProps {
  items: StatusItem[];
  className?: string;
}

export function VerificationStatus({
  items,
  className = "",
}: VerificationStatusProps) {
  const allCompleted = items.every((item) => item.completed);

  return (
    <Card className={className}>
      <CardContent className="pt-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4 flex-wrap">
            {items.map((item, index) => (
              <div key={index} className="flex items-center gap-2">
                <div
                  className={`w-3 h-3 rounded-full transition-colors ${
                    item.completed ? "bg-green-500" : "bg-gray-300"
                  }`}
                />
                <span className="text-sm">{item.label}</span>
              </div>
            ))}
          </div>
          <Badge
            variant={allCompleted ? "default" : "secondary"}
            className={allCompleted ? "bg-green-600 text-white" : ""}
          >
            {allCompleted ? "Ready to Submit" : "Incomplete"}
          </Badge>
        </div>
      </CardContent>
    </Card>
  );
}
