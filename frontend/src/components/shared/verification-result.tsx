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
  Download,
  Share2,
  User,
  Shield,
} from "lucide-react";

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
}

export function VerificationResult({
  status,
  onRetry,
  onStartOver,
  verificationId,
  backendData,
}: VerificationResultProps) {
  const getStatusConfig = (status: VerificationStatus) => {
    const configs = {
      processing: {
        icon: <Clock className="w-12 h-12 text-blue-500 animate-pulse" />,
        title: "Verification in Progress",
        description:
          "We're analyzing your documents and verifying your identity. This may take a few moments.",
        bgColor: "bg-blue-50",
        borderColor: "border-blue-200",
        textColor: "text-blue-900",
      },
      success: {
        icon: <CheckCircle className="w-12 h-12 text-green-500" />,
        title: "Verification Successful",
        description:
          "Your identity has been successfully verified. All checks have passed.",
        bgColor: "bg-green-50",
        borderColor: "border-green-200",
        textColor: "text-green-900",
      },
      failed: {
        icon: <XCircle className="w-12 h-12 text-red-500" />,
        title: "Verification Failed",
        description:
          "We couldn't verify your identity. Please check the details below and try again.",
        bgColor: "bg-red-50",
        borderColor: "border-red-200",
        textColor: "text-red-900",
      },
      partial: {
        icon: <AlertTriangle className="w-12 h-12 text-yellow-500" />,
        title: "Partial Verification",
        description:
          "Some verification steps completed successfully, but others need attention.",
        bgColor: "bg-yellow-50",
        borderColor: "border-yellow-200",
        textColor: "text-yellow-900",
      },
    };
    return configs[status];
  };

  const config = getStatusConfig(status);

  const getConfidenceScore = () => {
    if (!backendData?.face_verification) return null;

    const distance = Number.parseFloat(backendData.face_verification.distance);
    const threshold = Number.parseFloat(
      backendData.face_verification.threshold
    );

    // Convert distance to confidence score (lower distance = higher confidence)
    const confidence = Math.max(
      0,
      Math.min(100, ((threshold - distance) / threshold) * 100)
    );
    return Math.round(confidence);
  };

  const getStepIcon = (passed: boolean) => {
    return passed ? (
      <div className="p-2 rounded-full bg-green-100">
        <CheckCircle className="w-4 h-4 text-green-500" />
      </div>
    ) : (
      <div className="p-2 rounded-full bg-red-100">
        <XCircle className="w-4 h-4 text-red-500" />
      </div>
    );
  };

  const confidenceScore = getConfidenceScore();

  return (
    <div className="space-y-6">
      {/* Main Status Card */}
      <Card className={`${config.bgColor} ${config.borderColor} border-2`}>
        <CardContent className="pt-8 pb-6">
          <div className="text-center space-y-4">
            <div className="flex justify-center">{config.icon}</div>
            <div>
              <h2 className={`text-2xl font-bold ${config.textColor} mb-2`}>
                {config.title}
              </h2>
              <p className={`${config.textColor} opacity-80`}>
                {config.description}
              </p>
            </div>

            {backendData?.overall_status && (
              <div className="pt-2">
                <p className={`text-sm ${config.textColor} font-medium`}>
                  {backendData.overall_status}
                </p>
              </div>
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
                  <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce"></div>
                  <div
                    className="w-2 h-2 bg-blue-500 rounded-full animate-bounce"
                    style={{ animationDelay: "0.1s" }}
                  ></div>
                  <div
                    className="w-2 h-2 bg-blue-500 rounded-full animate-bounce"
                    style={{ animationDelay: "0.2s" }}
                  ></div>
                </div>
                <p className="text-sm text-blue-600 mt-2">
                  Estimated time: 30-60 seconds
                </p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Extracted Information */}
      {backendData?.text_details && status === "success" && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <User className="w-5 h-5 text-blue-600" />
              Extracted Information
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-sm font-medium text-gray-600">
                    Name:
                  </span>
                  <span className="text-sm font-bold">
                    {backendData.text_details.name}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm font-medium text-gray-600">
                    Date of Birth:
                  </span>
                  <span className="text-sm font-bold">
                    {backendData.text_details.dob}
                  </span>
                </div>
              </div>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-sm font-medium text-gray-600">
                    Document Type:
                  </span>
                  <span className="text-sm font-bold">
                    {backendData.text_details.card_type}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm font-medium text-gray-600">
                    Document Number:
                  </span>
                  <span className="text-sm font-bold">
                    {backendData.text_details.aadhaar_no}
                  </span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Detailed Verification Steps */}
      {backendData &&
        (status === "success" ||
          status === "failed" ||
          status === "partial") && (
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Shield className="w-5 h-5 text-indigo-600" />
                Verification Details
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Document Processing */}
              <div className="flex items-center justify-between p-3 rounded-lg bg-gray-50">
                <div className="flex items-center space-x-3">
                  {getStepIcon(
                    backendData.id_card_processing_status?.includes(
                      "Successfully"
                    ) || false
                  )}
                  <div>
                    <span className="font-medium">Document Processing</span>
                    <p className="text-xs text-gray-600">
                      Text extraction and validation
                    </p>
                  </div>
                </div>
                <Badge
                  variant={
                    backendData.id_card_processing_status?.includes(
                      "Successfully"
                    )
                      ? "default"
                      : "destructive"
                  }
                >
                  {backendData.id_card_processing_status?.includes(
                    "Successfully"
                  )
                    ? "Passed"
                    : "Failed"}
                </Badge>
              </div>

              {/* Liveness Check */}
              {backendData.liveness_check && (
                <div className="flex items-center justify-between p-3 rounded-lg bg-gray-50">
                  <div className="flex items-center space-x-3">
                    {getStepIcon(backendData.liveness_check.passed)}
                    <div>
                      <span className="font-medium">Liveness Detection</span>
                      <p className="text-xs text-gray-600">
                        Real person verification
                      </p>
                    </div>
                  </div>
                  <Badge
                    variant={
                      backendData.liveness_check.passed
                        ? "default"
                        : "destructive"
                    }
                  >
                    {backendData.liveness_check.status}
                  </Badge>
                </div>
              )}

              {/* Face Verification */}
              {backendData.face_verification && (
                <div className="flex items-center justify-between p-3 rounded-lg bg-gray-50">
                  <div className="flex items-center space-x-3">
                    {getStepIcon(backendData.face_verification.verified)}
                    <div>
                      <span className="font-medium">Face Matching</span>
                      <p className="text-xs text-gray-600">
                        {backendData.face_verification.model} • Distance:{" "}
                        {backendData.face_verification.distance}
                      </p>
                    </div>
                  </div>
                  <Badge
                    variant={
                      backendData.face_verification.verified
                        ? "default"
                        : "destructive"
                    }
                  >
                    {backendData.face_verification.verified
                      ? "Matched"
                      : "No Match"}
                  </Badge>
                </div>
              )}

              {/* Database Storage */}
              {backendData.database_storage && (
                <div className="flex items-center justify-between p-3 rounded-lg bg-gray-50">
                  <div className="flex items-center space-x-3">
                    {getStepIcon(backendData.database_storage.stored)}
                    <div>
                      <span className="font-medium">Data Storage</span>
                      <p className="text-xs text-gray-600">
                        Secure database storage
                      </p>
                    </div>
                  </div>
                  <Badge
                    variant={
                      backendData.database_storage.stored
                        ? "default"
                        : "destructive"
                    }
                  >
                    {backendData.database_storage.stored ? "Stored" : "Failed"}
                  </Badge>
                </div>
              )}

              {/* Confidence Score */}
              {confidenceScore !== null && (
                <div className="pt-4 border-t">
                  <div className="flex items-center justify-between">
                    <span className="font-medium">Confidence Score</span>
                    <div className="flex items-center space-x-2">
                      <div className="w-32 bg-gray-200 rounded-full h-2">
                        <div
                          className={`h-2 rounded-full ${
                            confidenceScore >= 80
                              ? "bg-green-500"
                              : confidenceScore >= 60
                              ? "bg-yellow-500"
                              : "bg-red-500"
                          }`}
                          style={{ width: `${confidenceScore}%` }}
                        ></div>
                      </div>
                      <span className="font-bold">{confidenceScore}%</span>
                    </div>
                  </div>
                  <p className="text-xs text-gray-600 mt-1">
                    Threshold: {backendData.face_verification?.threshold} •
                    Metric: {backendData.face_verification?.metric}
                  </p>
                </div>
              )}

              {/* Error Messages */}
              {status === "failed" && (
                <div className="pt-4 border-t">
                  <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                    <h4 className="font-medium text-red-900 mb-2">
                      Verification Issues:
                    </h4>
                    <div className="space-y-1 text-red-800 text-sm">
                      {!backendData.liveness_check?.passed && (
                        <p>
                          • Liveness check failed - Please ensure you're a real
                          person in good lighting
                        </p>
                      )}
                      {!backendData.face_verification?.verified && (
                        <p>
                          • Face matching failed - The face in document doesn't
                          match the live photo
                        </p>
                      )}
                      {!backendData.database_storage?.stored && (
                        <p>• Data storage failed - Please try again</p>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        )}

      {/* Action Buttons */}
      <div className="flex flex-col sm:flex-row gap-3 justify-center">
        {status === "success" && (
          <>
            <Button className="bg-green-600 hover:bg-green-700 text-white">
              <Download className="w-4 h-4 mr-2" />
              Download Certificate
            </Button>
            <Button
              variant="outline"
              className="border-green-300 text-green-700 hover:bg-green-50"
            >
              <Share2 className="w-4 h-4 mr-2" />
              Share Result
            </Button>
          </>
        )}

        {(status === "failed" || status === "partial") && (
          <>
            {onRetry && (
              <Button
                onClick={onRetry}
                className="bg-blue-600 hover:bg-blue-700 text-white"
              >
                <RefreshCw className="w-4 h-4 mr-2" />
                Retry Verification
              </Button>
            )}
            {onStartOver && (
              <Button
                variant="outline"
                onClick={onStartOver}
                className="border-gray-300 text-gray-700 hover:bg-gray-50"
              >
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
