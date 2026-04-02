"use client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  CheckCircle,
  XCircle,
  Clock,
  AlertTriangle,
  RefreshCw,
  User,
  Shield,
  MinusCircle,
} from "lucide-react";
import type { PipelineStage } from "@/components/shared/pipeline-progress";

export type VerificationStatus =
  | "processing"
  | "success"
  | "failed"
  | "partial";

interface BackendResponse {
  database_storage?: {
    message: string;
    stored: boolean;
  };
  face_verification?: {
    distance: string;
    message: string;
    metric: string;
    model: string;
    status: string;
    threshold: string;
    verified: boolean;
  };
  id_card_processing_status?: string;
  liveness_check?: {
    passed: boolean;
    status: string;
  };
  overall_status?: string;
  text_details?: {
    aadhaar_no?: string;
    card_type?: string;
    dob?: string;
    name?: string;
  };
}

interface VerificationResultProps {
  status: VerificationStatus;
  onRetry?: () => void;
  onStartOver?: () => void;
  verificationId?: string;
  backendData?: BackendResponse;
  // NEW: completed pipeline stages from the SSE stream
  stages?: PipelineStage[];
}

// ── Stage icon by status ────────────────────────────────────────────────────────
function StageIcon({ status }: { status: PipelineStage["status"] }) {
  if (status === "passed")
    return (
      <div className="p-1.5 rounded-full bg-green-100 flex-shrink-0">
        <CheckCircle className="w-4 h-4 text-green-500" />
      </div>
    );
  if (status === "failed")
    return (
      <div className="p-1.5 rounded-full bg-red-100 flex-shrink-0">
        <XCircle className="w-4 h-4 text-red-500" />
      </div>
    );
  if (status === "skipped")
    return (
      <div className="p-1.5 rounded-full bg-gray-100 flex-shrink-0">
        <MinusCircle className="w-4 h-4 text-gray-400" />
      </div>
    );
  // waiting / running (shouldn't appear on result page, but safe fallback)
  return (
    <div className="p-1.5 rounded-full bg-gray-100 flex-shrink-0">
      <Clock className="w-4 h-4 text-gray-400" />
    </div>
  );
}

// ── Badge by status ─────────────────────────────────────────────────────────────
function StageBadge({ status }: { status: PipelineStage["status"] }) {
  const map: Record<PipelineStage["status"], { label: string; cls: string }> = {
    passed:  { label: "Passed",   cls: "bg-green-100 text-green-700 border border-green-200" },
    failed:  { label: "Failed",   cls: "bg-red-100 text-red-700 border border-red-200" },
    skipped: { label: "Skipped",  cls: "bg-gray-100 text-gray-500 border border-gray-200" },
    waiting: { label: "Waiting",  cls: "bg-gray-100 text-gray-400 border border-gray-200" },
    running: { label: "Running",  cls: "bg-blue-100 text-blue-700 border border-blue-200" },
  };
  const { label, cls } = map[status];
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium whitespace-nowrap ${cls}`}>
      {label}
    </span>
  );
}

// ── Row bg by status ────────────────────────────────────────────────────────────
function rowBg(status: PipelineStage["status"]) {
  if (status === "passed")  return "bg-green-50 border border-green-100";
  if (status === "failed")  return "bg-red-50 border border-red-200";
  if (status === "skipped") return "bg-gray-50 opacity-60 border border-gray-100";
  return "bg-gray-50";
}

export function VerificationResult({
  status,
  onRetry,
  onStartOver,
  verificationId,
  backendData,
  stages,
}: VerificationResultProps) {

  // ── Status card config ────────────────────────────────────────────────────────
  const statusConfig = {
    processing: {
      icon: <Clock className="w-12 h-12 text-blue-500 animate-pulse" />,
      title: "Verification in Progress",
      description: "We're analyzing your documents and verifying your identity.",
      bgColor: "bg-blue-50", borderColor: "border-blue-200", textColor: "text-blue-900",
    },
    success: {
      icon: <CheckCircle className="w-12 h-12 text-green-500" />,
      title: "Verification Successful",
      description: "Your identity has been successfully verified. All checks have passed.",
      bgColor: "bg-green-50", borderColor: "border-green-200", textColor: "text-green-900",
    },
    failed: {
      icon: <XCircle className="w-12 h-12 text-red-500" />,
      title: "Verification Failed",
      description: "We couldn't verify your identity. See the stage breakdown below for the exact reason.",
      bgColor: "bg-red-50", borderColor: "border-red-200", textColor: "text-red-900",
    },
    partial: {
      icon: <AlertTriangle className="w-12 h-12 text-yellow-500" />,
      title: "Partial Verification",
      description: "Some steps passed, but one or more stages need attention.",
      bgColor: "bg-yellow-50", borderColor: "border-yellow-200", textColor: "text-yellow-900",
    },
  };

  const config = statusConfig[status];

  // ── Find the stage that caused failure (for the callout box) ─────────────────
  const failedStage = stages?.find((s) => s.status === "failed");

  // ── Fallback stages derived from backendData (when no SSE stages available) ──
  const fallbackStages: PipelineStage[] | undefined = backendData
    ? [
        {
          id: "document",
          title: "Document Processing",
          description: "OCR extraction & validation",
          status: backendData.id_card_processing_status?.includes("Successfully") ? "passed" : "failed",
          detail: backendData.id_card_processing_status,
        },
        {
          id: "liveness",
          title: "Liveness Detection",
          description: "Real person verification",
          status: backendData.liveness_check
            ? backendData.liveness_check.passed ? "passed" : "failed"
            : "skipped",
          detail: backendData.liveness_check?.status,
        },
        {
          id: "face_match",
          title: "Face Matching",
          description: backendData.face_verification
            ? `${backendData.face_verification.model} • Distance: ${backendData.face_verification.distance}`
            : "Cosine similarity check",
          status: backendData.face_verification
            ? backendData.face_verification.verified ? "passed" : "failed"
            : "skipped",
          detail: backendData.face_verification?.message,
        },
        {
          id: "storage",
          title: "Data Storage",
          description: "Secure database persistence",
          status: backendData.database_storage
            ? backendData.database_storage.stored ? "passed" : "failed"
            : "skipped",
          detail: backendData.database_storage?.message,
        },
      ]
    : undefined;

  const displayStages = stages ?? fallbackStages;

  return (
    <div className="space-y-6">

      {/* ── Main Status Banner ──────────────────────────────────────────────── */}
      <Card className={`${config.bgColor} ${config.borderColor} border-2`}>
        <CardContent className="pt-8 pb-6">
          <div className="text-center space-y-4">
            <div className="flex justify-center">{config.icon}</div>
            <div>
              <h2 className={`text-2xl font-bold ${config.textColor} mb-2`}>{config.title}</h2>
              <p className={`${config.textColor} opacity-80`}>{config.description}</p>
            </div>

            {backendData?.overall_status && (
              <p className={`text-sm ${config.textColor} font-medium pt-2`}>
                {backendData.overall_status}
              </p>
            )}

            {verificationId && (
              <div className="pt-4">
                <Badge variant="secondary" className="text-xs">
                  Verification ID: {verificationId}
                </Badge>
              </div>
            )}

            {status === "processing" && (
              <div className="pt-4">
                <div className="flex items-center justify-center space-x-2">
                  {[0, 0.1, 0.2].map((delay, i) => (
                    <div
                      key={i}
                      className="w-2 h-2 bg-blue-500 rounded-full animate-bounce"
                      style={{ animationDelay: `${delay}s` }}
                    />
                  ))}
                </div>
                <p className="text-sm text-blue-600 mt-2">Estimated time: 30–60 seconds</p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* ── Failure Reason Callout (only on failed, from the exact failing stage) */}
      {status === "failed" && failedStage && (
        <div className="bg-red-50 border border-red-300 rounded-xl p-4 flex gap-3">
          <XCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-semibold text-red-800">
              Failed at: {failedStage.title}
            </p>
            <p className="text-sm text-red-700 mt-0.5">{failedStage.detail}</p>
          </div>
        </div>
      )}

      {/* ── Extracted Information (success only) ──────────────────────────────── */}
      {backendData?.text_details && status === "success" && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <User className="w-5 h-5 text-blue-600" />
              Extracted Information
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-sm font-medium text-gray-600">Name:</span>
                  <span className="text-sm font-bold">{backendData.text_details.name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm font-medium text-gray-600">Date of Birth:</span>
                  <span className="text-sm font-bold">{backendData.text_details.dob}</span>
                </div>
              </div>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-sm font-medium text-gray-600">Document Type:</span>
                  <span className="text-sm font-bold">{backendData.text_details.card_type}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm font-medium text-gray-600">Document Number:</span>
                  <span className="text-sm font-bold">{backendData.text_details.aadhaar_no}</span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── Pipeline Stage Breakdown ───────────────────────────────────────────── */}
      {displayStages && (status === "success" || status === "failed" || status === "partial") && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Shield className="w-5 h-5 text-indigo-600" />
              Verification Details
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {displayStages.map((stage, index) => (
              <div key={stage.id} className="relative">
                {/* Connector */}
                {index < displayStages.length - 1 && (
                  <div className="absolute left-[22px] top-[48px] w-0.5 h-3 bg-gray-200 z-0" />
                )}

                <div className={`relative z-10 flex items-start gap-3 p-3 rounded-lg transition-all ${rowBg(stage.status)}`}>
                  <StageIcon status={stage.status} />

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <div>
                        <span className="font-medium text-sm text-gray-800">{stage.title}</span>
                        <p className="text-xs text-gray-500">{stage.description}</p>
                      </div>
                      <StageBadge status={stage.status} />
                    </div>

                    {/* Detail message — shown for passed/failed/skipped */}
                    {stage.detail && stage.status !== "waiting" && (
                      <div className={`mt-2 text-xs px-3 py-1.5 rounded-md font-mono break-words ${
                        stage.status === "failed"
                          ? "bg-red-100 text-red-700"
                          : stage.status === "skipped"
                          ? "bg-gray-100 text-gray-500"
                          : "bg-green-100 text-green-700"
                      }`}>
                        {stage.detail}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}


          </CardContent>
        </Card>
      )}

      {/* ── Action Buttons ─────────────────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row gap-3 justify-center">
        {(status === "failed" || status === "partial") && (
          <>
            {onRetry && (
              <Button onClick={onRetry} className="bg-blue-600 hover:bg-blue-700 text-white">
                <RefreshCw className="w-4 h-4 mr-2" />
                Retry Verification
              </Button>
            )}
            {onStartOver && (
              <Button variant="outline" onClick={onStartOver} className="border-gray-300 text-gray-700 hover:bg-gray-50">
                Start Over
              </Button>
            )}
          </>
        )}

        {status === "processing" && (
          <Button variant="outline" disabled className="cursor-not-allowed">
            <Clock className="w-4 h-4 mr-2" />
            Please Wait...
          </Button>
        )}
      </div>
    </div>
  );
}
