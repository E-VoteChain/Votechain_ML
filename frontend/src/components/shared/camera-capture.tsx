import { useState, useRef, useEffect } from "react";
import { Camera, X, RotateCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface CameraCaptureProps {
  onCapture: (imageSrc: string) => void;
  onClose: () => void;
  className?: string;
}

export function CameraCapture({
  onCapture,
  onClose,
  className,
}: CameraCaptureProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [isCameraReady, setIsCameraReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [facingMode, setFacingMode] = useState<"user" | "environment">("user");

  useEffect(() => {
    startCamera();
    return () => {
      stopCamera();
    };
  }, [facingMode]);

  const startCamera = async () => {
    try {
      setError(null);
      const constraints = {
        video: {
          facingMode: facingMode,
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
      };

      const mediaStream = await navigator.mediaDevices.getUserMedia(
        constraints
      );
      setStream(mediaStream);

      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream;
        videoRef.current.onloadedmetadata = () => {
          setIsCameraReady(true);
        };
      }
    } catch (err) {
      console.error("Error accessing camera:", err);
      setError(
        "Could not access camera. Please ensure you've granted camera permissions."
      );
    }
  };

  const stopCamera = () => {
    if (videoRef.current && videoRef.current.srcObject) {
      const mediaStream = videoRef.current.srcObject as MediaStream;
      mediaStream.getTracks().forEach((track) => {
        track.stop();
      });
    }

    if (stream) {
      stream.getTracks().forEach((track) => {
        track.stop();
      });
      setStream(null);
    }

    setIsCameraReady(false);
  };

  const switchCamera = () => {
    stopCamera();
    setFacingMode((prev) => (prev === "user" ? "environment" : "user"));
  };

  const capturePhoto = () => {
    if (!isCameraReady || !videoRef.current || !canvasRef.current) return;

    const video = videoRef.current;
    const canvas = canvasRef.current;
    const context = canvas.getContext("2d");

    if (!context) return;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    context.drawImage(video, 0, 0, canvas.width, canvas.height);

    const imageSrc = canvas.toDataURL("image/png");

    onCapture(imageSrc);

    stopCamera();
  };

  return (
    <div
      className={cn("relative bg-black rounded-lg overflow-hidden", className)}
    >
      {/* Close button */}
      <Button
        variant="ghost"
        size="icon"
        className="absolute top-2 right-2 z-10 bg-black/50 text-white hover:bg-black/70 hover:text-white"
        onClick={() => {
          stopCamera();
          setTimeout(() => {
            onClose();
          }, 100);
        }}
      >
        <X className="h-5 w-5" />
      </Button>

      <div className="relative aspect-1 max-h-[80vh] flex items-center justify-center bg-black">
        {error ? (
          <div className="text-white text-center p-4">
            <p>{error}</p>
            <Button
              variant="outline"
              className="mt-4 bg-white/10 text-white"
              onClick={startCamera}
            >
              Try Again
            </Button>
          </div>
        ) : (
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            className={cn(
              "w-full h-full object-cover",
              facingMode === "user" ? "scale-x-[-1]" : ""
            )}
          />
        )}

        <canvas ref={canvasRef} className="hidden" />
      </div>

      <div className="p-4 bg-black flex items-center justify-between">
        <Button
          variant="outline"
          size="icon"
          className="bg-white/10 text-white border-white/20 hover:bg-white/20 hover:text-white"
          onClick={switchCamera}
          disabled={!isCameraReady}
        >
          <RotateCw className="h-5 w-5" />
        </Button>
        <Button
          variant="default"
          size="lg"
          className="rounded-full w-16 h-16 p-0 bg-white text-black hover:bg-white/90"
          onClick={capturePhoto}
          disabled={!isCameraReady}
        >
          <Camera className="h-6 w-6" />
        </Button>
        <div className="w-10" />
      </div>
    </div>
  );
}
