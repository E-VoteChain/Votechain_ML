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
import axios from "axios";

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

export default function IdentityVerification() {
  const [documentImage, setDocumentImage] = useState<File | null>(null);
  const [faceImage, setFaceImage] = useState<File | null>(null);
  const [documentPreview, setDocumentPreview] = useState<string | null>(null);
  const [facePreview, setFacePreview] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showCamera, setShowCamera] = useState(false);
  const [responseMsg, setResponseMsg] = useState("");
  const [backendResponse, setBackendResponse] =
    useState<BackendResponse | null>(null);
  const [verificationStatus, setVerificationStatus] =
    useState<VerificationStatusType | null>(null);

  const handleDocumentUpload = (file: File) => {
    setDocumentImage(file);
    const reader = new FileReader();
    reader.onload = (e) => {
      setDocumentPreview(e.target?.result as string);
    };
    reader.readAsDataURL(file);
  };

  const handleCameraCapture = (imageSrc: string) => {
    fetch(imageSrc)
      .then((res) => res.blob())
      .then((blob) => {
        const file = new File([blob], "profile-photo.png", {
          type: "image/png",
        });
        setFaceImage(file);
        setFacePreview(imageSrc);
        setShowCamera(false);
      });
  };

  const determineVerificationStatus = (
    response: BackendResponse
  ): VerificationStatusType => {
    const livenessPass = response.liveness_check?.passed ?? false;
    const faceVerified = response.face_verification?.verified ?? false;
    const dataStored = response.database_storage?.stored ?? false;
    const docProcessed =
      response.id_card_processing_status?.includes("Successfully") ?? false;

    // All checks passed
    if (livenessPass && faceVerified && dataStored && docProcessed) {
      return "success";
    }

    // Some checks passed
    if (livenessPass || faceVerified || dataStored || docProcessed) {
      return "partial";
    }

    // All checks failed
    return "failed";
  };

  const handleSubmit = async () => {
    if (!documentImage || !faceImage) {
      toast.error("Please upload both document and face images");
      return;
    }

    setIsSubmitting(true);
    setVerificationStatus("processing");

    const formData = new FormData();
    formData.append("id_card_image", documentImage);
    formData.append("live_face_image", faceImage);

    try {
      const response = await axios.post(
        "http://localhost:5000/process_and_verify",
        formData,
        {
          headers: {
            "Content-Type": "multipart/form-data",
          },
        }
      );

      const responseData = response.data as BackendResponse;
      console.log("ResponseData", responseData);
      setBackendResponse(responseData);

      const status = determineVerificationStatus(responseData);
      setVerificationStatus(status);

      if (status === "success") {
        toast.success("Identity verification completed successfully!");
      } else if (status === "partial") {
        toast.warning("Verification completed with some issues");
      } else {
        toast.error("Verification failed. Please try again.");
      }
    } catch (error) {
      console.error("Error sending data:", error);
      toast.error("Failed to submit verification. Please try again.");
      setVerificationStatus("failed");
      setBackendResponse(null);
    } finally {
      setIsSubmitting(false);
    }
  };

  const removeDocumentImage = () => {
    setDocumentImage(null);
    setDocumentPreview(null);
  };

  const removeFaceImage = () => {
    setFaceImage(null);
    setFacePreview(null);
  };

  const openCamera = () => {
    setShowCamera(true);
  };

  const statusItems = [
    { label: "Document Uploaded", completed: !!documentImage },
    { label: "Face Image Captured", completed: !!faceImage },
  ];

  const handleRetry = () => {
    setVerificationStatus(null);
    setBackendResponse(null);
  };

  const handleStartOver = () => {
    setDocumentImage(null);
    setFaceImage(null);
    setDocumentPreview(null);
    setFacePreview(null);
    setVerificationStatus(null);
    setBackendResponse(null);
  };

  if (verificationStatus) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-purple-50 to-pink-50 p-4">
        <div className="max-w-4xl mx-auto">
          <div className="mb-6">
            <Button
              variant="outline"
              onClick={() => setVerificationStatus(null)}
              className="border-gray-300 text-gray-700 hover:bg-gray-50"
            >
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back to Upload
            </Button>
          </div>

          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold text-gray-900 mb-2">
              Verification Results
            </h1>
            <p className="text-gray-600">
              Here are the results of your identity verification
            </p>
          </div>

          <VerificationResult
            status={verificationStatus}
            onRetry={handleRetry}
            onStartOver={handleStartOver}
            verificationId={`VER-${Date.now().toString().slice(-8)}`}
            backendData={backendResponse ?? undefined}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-purple-50 to-pink-50 p-4">
      <div className="max-w-4xl mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Identity Verification
          </h1>
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
              onRetake={openCamera}
              acceptDrop={false}
              showRetake={!!facePreview}
              badgeText="Live Photo Captured"
              primaryColor="purple"
              ayush={false}
            />

            {!facePreview && (
              <Button
                type="button"
                variant="outline"
                onClick={() => setShowCamera(true)}
                className="flex items-center"
              >
                <Camera className="h-4 w-4 mr-2" />
                Take Photo
              </Button>
            )}
          </div>
        </div>
        <Dialog open={showCamera} onOpenChange={setShowCamera}>
          <DialogTitle className="sr-only">Capture Profile Image</DialogTitle>
          <DialogContent className="p-0 max-w-md overflow-hidden">
            <CameraCapture
              onCapture={handleCameraCapture}
              onClose={() => setShowCamera(false)}
            />
          </DialogContent>
        </Dialog>

        <VerificationStatus items={statusItems} className="mb-6" />
        {responseMsg}

        <div className="text-center mb-8">
          <Button
            onClick={handleSubmit}
            disabled={!documentImage || !faceImage || isSubmitting}
            size="lg"
            className="px-8 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white disabled:bg-gray-400 disabled:text-gray-200 disabled:from-gray-400 disabled:to-gray-400"
          >
            {isSubmitting ? (
              <>
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin mr-2" />
                Processing...
              </>
            ) : (
              <>
                <Eye className="w-4 h-4 mr-2" />
                Submit for Verification
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
