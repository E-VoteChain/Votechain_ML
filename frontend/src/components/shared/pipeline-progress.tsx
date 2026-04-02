"use client";
import { CheckCircle, XCircle, Loader2, Circle, FileText, Eye, User, Database } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export type StageStatus = "waiting" | "running" | "passed" | "failed" | "skipped";

export interface SubStep {
  id: string;       // "ocr" | "face"
  title: string;
  status: StageStatus;
  detail?: string;
}

export interface PipelineStage {
  id: string;
  title: string;
  description: string;
  status: StageStatus;
  detail?: string;
  subSteps?: SubStep[];   // only used by the document stage
}

interface PipelineProgressProps {
  stages: PipelineStage[];
}

const statusConfig: Record<
  StageStatus,
  { badge: string; badgeClass: string; icon: React.ReactNode; rowClass: string }
> = {
  waiting: {
    badge: "Waiting",
    badgeClass: "bg-gray-100 text-gray-500 border border-gray-200",
    icon: <Circle className="w-5 h-5 text-gray-300" />,
    rowClass: "bg-gray-50 opacity-60",
  },
  running: {
    badge: "Processing...",
    badgeClass: "bg-blue-100 text-blue-700 border border-blue-200",
    icon: <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />,
    rowClass: "bg-blue-50 border border-blue-200 shadow-sm",
  },
  passed: {
    badge: "Passed",
    badgeClass: "bg-green-100 text-green-700 border border-green-200",
    icon: (
      <div className="rounded-full bg-green-100 p-1">
        <CheckCircle className="w-5 h-5 text-green-500" />
      </div>
    ),
    rowClass: "bg-white border border-green-100",
  },
  failed: {
    badge: "Failed",
    badgeClass: "bg-red-100 text-red-700 border border-red-200",
    icon: (
      <div className="rounded-full bg-red-100 p-1">
        <XCircle className="w-5 h-5 text-red-500" />
      </div>
    ),
    rowClass: "bg-red-50 border border-red-200",
  },
  skipped: {
    badge: "Skipped",
    badgeClass: "bg-yellow-50 text-yellow-600 border border-yellow-200",
    icon: <Circle className="w-5 h-5 text-yellow-300" />,
    rowClass: "bg-gray-50 opacity-50",
  },
};

function SubStepIcon({ status }: { status: StageStatus }) {
  if (status === "running")
    return <Loader2 className="w-3.5 h-3.5 text-blue-500 animate-spin flex-shrink-0" />;
  if (status === "passed")
    return <CheckCircle className="w-3.5 h-3.5 text-green-500 flex-shrink-0" />;
  if (status === "failed")
    return <XCircle className="w-3.5 h-3.5 text-red-500 flex-shrink-0" />;
  return <Circle className="w-3.5 h-3.5 text-gray-300 flex-shrink-0" />;
}

function SubStepBadge({ status }: { status: StageStatus }) {
  const map: Record<StageStatus, { label: string; cls: string }> = {
    waiting: { label: "Waiting",    cls: "bg-gray-100 text-gray-400 border border-gray-200" },
    running: { label: "Running...", cls: "bg-blue-100 text-blue-600 border border-blue-200" },
    passed:  { label: "Done",       cls: "bg-green-100 text-green-600 border border-green-200" },
    failed:  { label: "Failed",     cls: "bg-red-100 text-red-600 border border-red-200" },
    skipped: { label: "Skipped",    cls: "bg-gray-100 text-gray-400 border border-gray-200" },
  };
  const { label, cls } = map[status];
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium whitespace-nowrap ${cls}`}>
      {label}
    </span>
  );
}

function detailClass(status: StageStatus) {
  if (status === "failed")  return "bg-red-100 text-red-700";
  if (status === "passed")  return "bg-green-100 text-green-700";
  if (status === "running") return "bg-blue-100 text-blue-700";
  return "bg-gray-100 text-gray-500";
}

export function PipelineProgress({ stages }: PipelineProgressProps) {
  const runningStage = stages.find((s) => s.status === "running");
  const allDone   = stages.every((s) => s.status !== "waiting" && s.status !== "running");
  const anyFailed = stages.some((s) => s.status === "failed");

  return (
    <Card className="w-full max-w-2xl mx-auto shadow-md">
      <CardHeader className="pb-2">
        <CardTitle className="text-lg flex items-center gap-2 text-gray-800">
          <div className="p-1.5 rounded-full bg-indigo-100">
            <Loader2 className={`w-4 h-4 text-indigo-600 ${!allDone ? "animate-spin" : ""}`} />
          </div>
          {allDone
            ? anyFailed ? "Verification Failed" : "Verification Complete"
            : `Processing — ${runningStage?.title ?? "Initializing..."}`}
        </CardTitle>
      </CardHeader>

      <CardContent className="space-y-3 pt-2">
        {stages.map((stage, index) => {
          const cfg = statusConfig[stage.status];
          return (
            <div key={stage.id} className="relative">
              {index < stages.length - 1 && (
                <div className="absolute left-[22px] top-[48px] w-0.5 h-3 bg-gray-200 z-0" />
              )}

              <div className={`relative z-10 flex items-start gap-3 p-3 rounded-lg transition-all duration-300 ${cfg.rowClass}`}>
                <div className="flex-shrink-0 pt-0.5">{cfg.icon}</div>

                <div className="flex-1 min-w-0">
                  {/* Title + badge */}
                  <div className="flex items-center justify-between gap-2">
                    <div>
                      <span className="font-medium text-sm text-gray-800">{stage.title}</span>
                      <p className="text-xs text-gray-500">{stage.description}</p>
                    </div>
                    <Badge className={`text-xs whitespace-nowrap px-2 py-0.5 rounded-full font-medium ${cfg.badgeClass}`}>
                      {cfg.badge}
                    </Badge>
                  </div>

                  {/* Stage-level detail chip */}
                  {stage.detail && stage.status !== "waiting" && (
                    <div className={`mt-2 text-xs px-3 py-1.5 rounded-md font-mono break-words ${detailClass(stage.status)}`}>
                      {stage.detail}
                    </div>
                  )}

                  {/* Running bar (only if no sub-steps visible yet) */}
                  {stage.status === "running" && !stage.subSteps?.some(s => s.status !== "waiting") && (
                    <div className="mt-2 h-1 w-full bg-blue-100 rounded-full overflow-hidden">
                      <div className="h-full bg-blue-400 rounded-full animate-pulse w-2/3" />
                    </div>
                  )}

                  {/* ── Sub-steps ────────────────────────────────────────────── */}
                  {stage.subSteps && stage.subSteps.some(s => s.status !== "waiting") && (
                    <div className="mt-3 space-y-2 pl-3 border-l-2 border-gray-200">
                      {stage.subSteps.map((sub) => (
                        <div key={sub.id} className="flex flex-col gap-1">
                          <div className="flex items-center justify-between gap-2">
                            <div className="flex items-center gap-2">
                              <SubStepIcon status={sub.status} />
                              <span className="text-xs font-medium text-gray-700">{sub.title}</span>
                            </div>
                            <SubStepBadge status={sub.status} />
                          </div>

                          {sub.detail && sub.status !== "waiting" && (
                            <div className={`ml-5 text-[11px] px-2.5 py-1 rounded font-mono break-words ${detailClass(sub.status)}`}>
                              {sub.detail}
                            </div>
                          )}

                          {sub.status === "running" && (
                            <div className="ml-5 mt-0.5 h-0.5 w-full bg-blue-100 rounded-full overflow-hidden">
                              <div className="h-full bg-blue-400 rounded-full animate-pulse w-2/3" />
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
