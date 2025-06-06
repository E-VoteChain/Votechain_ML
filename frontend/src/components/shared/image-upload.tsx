"use client";

import type React from "react";
import { useRef } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Upload, X, CheckCircle, RotateCcw, Camera } from "lucide-react";
import { toast } from "sonner";

interface ImageUploadProps {
  title: string;
  description: string;
  icon: React.ReactNode;
  file: File | null;
  preview: string | null;
  ayush: boolean;
  onFileSelect: (file: File) => void;
  onRemove: () => void;
  onRetake?: () => void;
  acceptDrop?: boolean;
  showRetake?: boolean;
  badgeText?: string;
  primaryColor?: string;
}

export function ImageUpload({
  title,
  description,
  icon,
  file,
  preview,
  ayush,
  onFileSelect,
  onRemove,
  onRetake,
  acceptDrop = true,
  showRetake = false,
  badgeText,
  primaryColor = "blue",
}: ImageUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFileUpload = (selectedFile: File) => {
    if (!selectedFile.type.startsWith("image/")) {
      toast.error("Please upload a valid image file");
      return;
    }

    if (selectedFile.size > 5 * 1024 * 1024) {
      toast.error("File size should be less than 5MB");
      return;
    }

    onFileSelect(selectedFile);
    toast.success("Image uploaded successfully");
  };

  const handleDrop = (e: React.DragEvent) => {
    if (!acceptDrop) return;

    e.preventDefault();
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      handleFileUpload(files[0]);
    }
  };

  const getColorClasses = (color: string) => {
    const colorMap = {
      blue: {
        border: "border-blue-400 hover:border-blue-500",
        bg: "hover:bg-blue-50",
        button: "bg-blue-600 hover:bg-blue-700 text-white",
        outline:
          "border-blue-300 text-blue-700 hover:bg-blue-50 hover:border-blue-400",
        icon: "text-blue-600",
      },
      green: {
        border: "border-green-400 hover:border-green-500",
        bg: "hover:bg-green-50",
        button: "bg-green-600 hover:bg-green-700 text-white",
        outline:
          "border-green-300 text-green-700 hover:bg-green-50 hover:border-green-400",
        icon: "text-green-600",
      },
      purple: {
        border: "border-purple-400 hover:border-purple-500",
        bg: "hover:bg-purple-50",
        button: "bg-purple-600 hover:bg-purple-700 text-white",
        outline:
          "border-purple-300 text-purple-700 hover:bg-purple-50 hover:border-purple-400",
        icon: "text-purple-600",
      },
    };
    return colorMap[color as keyof typeof colorMap] || colorMap.blue;
  };

  const colors = getColorClasses(primaryColor);

  return (
    <Card className="relative">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <span className={colors.icon}>{icon}</span>
          {title}
        </CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        <div
          className={`border-2 border-dashed rounded-lg p-6 text-center transition-colors ${
            preview
              ? "border-green-300 bg-green-50"
              : `border-gray-300 ${colors.border} ${colors.bg}`
          }`}
          onDrop={handleDrop}
          onDragOver={(e) => e.preventDefault()}
        >
          {preview ? (
            <div className="space-y-4">
              <div className="relative inline-block">
                <img
                  src={preview || "/placeholder.svg"}
                  alt="Preview"
                  className="max-w-full h-32 object-cover rounded-lg"
                />
                <Button
                  variant="destructive"
                  size="icon"
                  className="absolute -top-2 -right-2 w-6 h-6 bg-red-500 hover:bg-red-600"
                  onClick={onRemove}
                >
                  <X className="w-4 h-4" />
                </Button>
              </div>
              <div className="flex items-center justify-center gap-2">
                <CheckCircle className="w-5 h-5 text-green-600" />
                <span className="text-sm font-medium text-green-700">
                  Image uploaded
                </span>
              </div>
              <div className="flex gap-2 justify-center flex-wrap">
                <Badge
                  variant="secondary"
                  className="bg-green-100 text-green-800"
                >
                  {badgeText || file?.name || "Image captured"}
                </Badge>
              </div>
              {showRetake && onRetake && (
                <Button
                  variant="outline"
                  onClick={onRetake}
                  className={colors.outline}
                >
                  <RotateCcw className="w-4 h-4 mr-2" />
                  Retake Photo
                </Button>
              )}
            </div>
          ) : (
            <div className="space-y-4">
              {ayush ? (
                <Upload className="w-12 h-12 text-gray-400 mx-auto" />
              ) : (
                <Camera className="w-12 h-12 text-gray-400 mx-auto" />
              )}
              {ayush ? (
                <div>
                  <p className="text-sm font-medium text-gray-700 mb-1">
                    {acceptDrop
                      ? "Drag and drop your image here"
                      : "Click to upload your image"}
                  </p>
                  <p className="text-xs text-gray-500">
                    {acceptDrop
                      ? "or click to browse"
                      : "Select from your device"}
                  </p>
                </div>
              ) : (
                <div>
                  <p className="text-sm font-medium text-gray-700 mb-1">
                    Take a live photo using your camera
                  </p>
                  <p className="text-xs text-gray-500">
                    Click the button below to open camera
                  </p>
                </div>
              )}
              {ayush && (
                <Button
                  variant="outline"
                  onClick={() => inputRef.current?.click()}
                  className={colors.outline}
                >
                  Choose File
                </Button>
              )}
            </div>
          )}
          <input
            ref={inputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => {
              const selectedFile = e.target.files?.[0];
              if (selectedFile) handleFileUpload(selectedFile);
            }}
          />
        </div>
      </CardContent>
    </Card>
  );
}
