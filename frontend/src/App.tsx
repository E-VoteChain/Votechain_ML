import { useState } from "react";
import { Button } from "@/components/ui/button";
import { FileText, User, Eye, Camera, ArrowLeft } from "lucide-react";
import { toast } from "sonner";
import { CameraCapture } from "@/components/shared/camera-capture";
import { ImageUpload } from "@/components/shared/image-upload";
import { VerificationStatus } from "@/components/shared/verification-status";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import {
  VerificationResult,
  type VerificationStatus as VerificationStatusType,
} from "@/components/shared/verification-result";
import {
  PipelineProgress,
  type PipelineStage,
  type SubStep,
} from "@/components/shared/pipeline-progress";

interface BackendResponse {
  database_storage?: { message: string; stored: boolean };
  face_verification?: {
    distance: string; message: string; metric: string;
    model: string; status: string; threshold: string; verified: boolean;
  };
  id_card_processing_status?: string;
  liveness_check?: { passed: boolean; status: string };
  overall_status?: string;
  text_details?: {
    aadhaar_no?: string; card_type?: string; dob?: string; name?: string;
  };
}

// SSE event shape
interface SSEEvent {
  stage:    "document" | "liveness" | "face_match" | "storage" | "done";
  substage?: "ocr" | "face";        // only for document stage
  status:   "running" | "passed" | "failed" | "skipped";
  detail?:  string;
  overall?: "success" | "failed";
  data?:    BackendResponse;
}

// Sub-step definitions for the document stage
const DOC_SUBSTEPS: SubStep[] = [
  {
    id: "ocr",
    title: "Gemini OCR — text extraction",
    status: "waiting",
  },
  {
    id: "face",
    title: "Face extraction — RetinaFace → CLAHE → Facenet embedding",
    status: "waiting",
  },
];

const INITIAL_STAGES: PipelineStage[] = [
  {
    id: "document",
    title: "Document Processing",
    description: "OCR extraction & face embedding from ID card",
    status: "waiting",
    subSteps: DOC_SUBSTEPS.map((s) => ({ ...s })),
  },
  {
    id: "liveness",
    title: "Liveness Detection",
    description: "Real person verification (anti-spoofing)",
    status: "waiting",
  },
  {
    id: "face_match",
    title: "Face Matching",
    description: "Cosine similarity against ID photo embedding",
    status: "waiting",
  },
  {
    id: "storage",
    title: "Data Storage",
    description: "Secure database persistence",
    status: "waiting",
  },
];

export default function IdentityVerification() {
  const [documentImage, setDocumentImage] = useState<File | null>(null);
  const [faceImage, setFaceImage]         = useState<File | null>(null);
  const [documentPreview, setDocumentPreview] = useState<string | null>(null);
  const [facePreview, setFacePreview]         = useState<string | null>(null);
  const [showCamera, setShowCamera]       = useState(false);
  const [backendResponse, setBackendResponse] = useState<BackendResponse | null>(null);
  const [verificationStatus, setVerificationStatus] = useState<VerificationStatusType | null>(null);
  const [isStreaming, setIsStreaming]     = useState(false);
  const [stages, setStages]               = useState<PipelineStage[]>(INITIAL_STAGES);
  const [completedStages, setCompletedStages] = useState<PipelineStage[]>([]);

  // ── Helpers ────────────────────────────────────────────────────────────────
  /** Update a top-level stage by id */
  const patchStage = (
    prev: PipelineStage[],
    id: string,
    patch: Partial<PipelineStage>
  ): PipelineStage[] =>
    prev.map((s) => (s.id === id ? { ...s, ...patch } : s));

  /** Update a sub-step inside the document stage */
  const patchSubStep = (
    prev: PipelineStage[],
    subId: string,
    patch: Partial<SubStep>
  ): PipelineStage[] =>
    prev.map((s) => {
      if (s.id !== "document" || !s.subSteps) return s;
      return {
        ...s,
        subSteps: s.subSteps.map((sub) =>
          sub.id === subId ? { ...sub, ...patch } : sub
        ),
      };
    });

  const handleDocumentUpload = (file: File) => {
    setDocumentImage(file);
    const reader = new FileReader();
    reader.onload = (e) => setDocumentPreview(e.target?.result as string);
    reader.readAsDataURL(file);
  };

  const handleCameraCapture = (imageSrc: string) => {
    fetch(imageSrc)
      .then((r) => r.blob())
      .then((blob) => {
        const file = new File([blob], "profile-photo.png", { type: "image/png" });
        setFaceImage(file);
        setFacePreview(imageSrc);
        setShowCamera(false);
      });
  };

  const removeDocumentImage = () => { setDocumentImage(null); setDocumentPreview(null); };
  const removeFaceImage     = () => { setFaceImage(null);     setFacePreview(null); };

  // ── Submit → SSE stream ──────────────────────────────────────────────────
  const handleSubmit = async () => {
    if (!documentImage || !faceImage) {
      toast.error("Please upload both document and face images");
      return;
    }

    // Reset
    const freshStages = INITIAL_STAGES.map((s) => ({
      ...s,
      subSteps: s.subSteps ? s.subSteps.map((sub) => ({ ...sub })) : undefined,
    }));
    setStages(freshStages);
    setCompletedStages([]);
    setBackendResponse(null);
    setVerificationStatus(null);
    setIsStreaming(true);

    const formData = new FormData();
    formData.append("id_card_image",   documentImage);
    formData.append("live_face_image", faceImage);

    try {
      const response = await fetch(
        "http://localhost:5000/process_and_verify_stream",
        { method: "POST", body: formData }
      );

      if (!response.ok || !response.body) {
        throw new Error(`Server error: ${response.status}`);
      }

      const reader  = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer    = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() ?? "";

        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith("data: ")) continue;

          let event: SSEEvent;
          try { event = JSON.parse(line.slice(6)); }
          catch { continue; }

          if (event.stage === "done") {
            setCompletedStages((prev) => (prev.length ? prev : stages));
            setIsStreaming(false);
            if (event.data) setBackendResponse(event.data);
            setVerificationStatus(event.overall === "success" ? "success" : "failed");
            toast[event.overall === "success" ? "success" : "error"](
              event.overall === "success"
                ? "Identity verification completed successfully!"
                : "Verification failed. See details below."
            );
          } else if (event.substage) {
            // Sub-step event — update the sub-step inside document stage
            setStages((prev) => {
              const updated = patchSubStep(prev, event.substage!, {
                status: event.status,
                detail: event.detail,
              });
              setCompletedStages(updated);
              return updated;
            });
          } else {
            // Top-level stage event
            setStages((prev) => {
              const updated = patchStage(prev, event.stage, {
                status: event.status,
                detail: event.detail,
              });
              setCompletedStages(updated);
              return updated;
            });
          }
        }
      }
    } catch (err) {
      console.error("SSE stream error:", err);
      toast.error("Connection error. Please try again.");
      setIsStreaming(false);
      setVerificationStatus("failed");
    }
  };

  const reset = () => {
    setVerificationStatus(null);
    setBackendResponse(null);
    setStages(
      INITIAL_STAGES.map((s) => ({
        ...s,
        subSteps: s.subSteps ? s.subSteps.map((sub) => ({ ...sub })) : undefined,
      }))
    );
    setCompletedStages([]);
  };

  const handleRetry     = reset;
  const handleStartOver = () => {
    setDocumentImage(null); setFaceImage(null);
    setDocumentPreview(null); setFacePreview(null);
    reset();
  };

  const statusItems = [
    { label: "Document Uploaded",   completed: !!documentImage },
    { label: "Face Image Captured", completed: !!faceImage },
  ];

  // ── 1. RESULT PAGE ─────────────────────────────────────────────────────────
  if (verificationStatus) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-purple-50 to-pink-50 p-4">
        <div className="max-w-4xl mx-auto">
          <div className="mb-6">
            <Button variant="outline" onClick={() => setVerificationStatus(null)}
              className="border-gray-300 text-gray-700 hover:bg-gray-50">
              <ArrowLeft className="w-4 h-4 mr-2" /> Back to Upload
            </Button>
          </div>
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold text-gray-900 mb-2">Verification Results</h1>
            <p className="text-gray-600">Here are the results of your identity verification</p>
          </div>
          <VerificationResult
            status={verificationStatus}
            onRetry={handleRetry}
            onStartOver={handleStartOver}
            verificationId={`VER-${Date.now().toString().slice(-8)}`}
            backendData={backendResponse ?? undefined}
            stages={completedStages.length ? completedStages : undefined}
          />
        </div>
      </div>
    );
  }

  // ── 2. PIPELINE PROGRESS PAGE ──────────────────────────────────────────────
  if (isStreaming) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-purple-50 to-pink-50 p-4 flex flex-col items-center justify-center">
        <div className="w-full max-w-2xl space-y-6">
          <div className="text-center">
            <h1 className="text-3xl font-bold text-gray-900 mb-1">Verifying Identity</h1>
            <p className="text-gray-500 text-sm">
              Each stage runs sequentially — you'll see results in real time
            </p>
          </div>
          <PipelineProgress stages={stages} />
        </div>
      </div>
    );
  }

  // ── 3. UPLOAD PAGE ─────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-purple-50 to-pink-50 p-4">
      <div className="max-w-4xl mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Identity Verification</h1>
          <p className="text-gray-600">
            Upload your documents and take a live photo to verify your identity
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-6 mb-8">
          <ImageUpload
            title="Document Verification"
            description="Upload your Aadhar Card, PAN Card, or any government-issued ID"
            icon={<FileText className="w-5 h-5" />}
            file={documentImage}
            preview={documentPreview}
            onFileSelect={handleDocumentUpload}
            onRemove={removeDocumentImage}
            primaryColor="blue"
            ayush={true}
          />
          <div className="space-y-4">
            <ImageUpload
              title="Live Face Verification"
              description="Take a clear photo of your face for identity matching"
              icon={<User className="w-5 h-5" />}
              file={faceImage}
              preview={facePreview}
              onFileSelect={() => {}}
              onRemove={removeFaceImage}
              onRetake={() => setShowCamera(true)}
              acceptDrop={false}
              showRetake={!!facePreview}
              badgeText="Live Photo Captured"
              primaryColor="purple"
              ayush={false}
            />
            {!facePreview && (
              <Button type="button" variant="outline"
                onClick={() => setShowCamera(true)} className="flex items-center">
                <Camera className="h-4 w-4 mr-2" /> Take Photo
              </Button>
            )}
          </div>
        </div>

        <Dialog open={showCamera} onOpenChange={setShowCamera}>
          <DialogTitle className="sr-only">Capture Profile Image</DialogTitle>
          <DialogContent className="p-0 max-w-md overflow-hidden">
            <CameraCapture onCapture={handleCameraCapture}
              onClose={() => setShowCamera(false)} />
          </DialogContent>
        </Dialog>

        <VerificationStatus items={statusItems} className="mb-6" />

        <div className="text-center mb-8">
          <Button
            onClick={handleSubmit}
            disabled={!documentImage || !faceImage}
            size="lg"
            className="px-8 bg-gradient-to-r from-indigo-600 to-purple-600
              hover:from-indigo-700 hover:to-purple-700 text-white
              disabled:bg-gray-400 disabled:text-gray-200
              disabled:from-gray-400 disabled:to-gray-400"
          >
            <Eye className="w-4 h-4 mr-2" />
            Submit for Verification
          </Button>
        </div>
      </div>
    </div>
  );
}
