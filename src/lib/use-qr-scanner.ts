import { BrowserQRCodeReader, type IScannerControls } from "@zxing/browser";
import { useCallback, useEffect, useRef, useState } from "react";

const MATRIC_PATTERN = /^[A-Za-z]{2,6}\/[0-9]{2,4}\/[0-9]{3,6}$/;

export interface ScannerCamera {
  deviceId: string;
  label: string;
}

export function classifyKioskScan(value: string): "identifier" | "token" {
  const trimmed = value.trim();
  if (!trimmed) return "token";
  if (trimmed.includes("@") || MATRIC_PATTERN.test(trimmed)) return "identifier";
  return "token";
}

export function useQrScanner(onScan: (text: string) => void, scanning: boolean) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const controlsRef = useRef<IScannerControls | null>(null);
  const lastValue = useRef("");
  const [permissionError, setPermissionError] = useState<string | null>(null);
  const [facingMode, setFacingMode] = useState<"environment" | "user">("environment");
  const [cameras, setCameras] = useState<ScannerCamera[]>([]);
  const [selectedCameraId, setSelectedCameraId] = useState("");

  const stop = useCallback(() => {
    controlsRef.current?.stop();
    controlsRef.current = null;
    lastValue.current = "";
  }, []);

  const selectCamera = useCallback((deviceId: string) => {
    setSelectedCameraId(deviceId);
    if (!deviceId) setFacingMode("environment");
  }, []);

  const switchLens = useCallback(() => {
    if (cameras.length > 1) {
      const currentIndex = cameras.findIndex((camera) => camera.deviceId === selectedCameraId);
      const next = cameras[(currentIndex + 1) % cameras.length];
      if (next) setSelectedCameraId(next.deviceId);
      return;
    }
    setFacingMode((current) => current === "environment" ? "user" : "environment");
  }, [cameras, selectedCameraId]);

  useEffect(() => {
    if (!scanning) {
      stop();
      return;
    }

    let cancelled = false;
    setPermissionError(null);

    const start = async () => {
      await new Promise<void>((resolve) => window.requestAnimationFrame(() => resolve()));
      if (cancelled || !videoRef.current) return;

      try {
        const reader = new BrowserQRCodeReader();
        const videoConstraints: MediaTrackConstraints = selectedCameraId
          ? { deviceId: { exact: selectedCameraId } }
          : { facingMode: { ideal: facingMode } };
        const controls = await reader.decodeFromConstraints(
          { video: videoConstraints, audio: false },
          videoRef.current,
          (result) => {
            const text = result?.getText().trim();
            if (!text || text === lastValue.current) return;
            lastValue.current = text;
            onScan(text);
          },
        );

        if (cancelled) {
          controls.stop();
          return;
        }
        controlsRef.current = controls;

        // Device labels are normally hidden until camera permission is granted.
        const devices = await navigator.mediaDevices.enumerateDevices();
        if (cancelled) return;
        const available = devices
          .filter((device) => device.kind === "videoinput" && device.deviceId)
          .map((device, index) => ({
            deviceId: device.deviceId,
            label: device.label.trim() || `Camera ${index + 1}`,
          }));
        setCameras(available);

        // Keep the rear camera as the default on phones, but allow selecting
        // every enumerated lens (macro, ultra-wide, telephoto, front, etc.).
        if (!selectedCameraId && available.length > 1) {
          const rearCamera = available.find((camera) => /back|rear|environment|world/i.test(camera.label));
          const preferredCamera = rearCamera || available[available.length - 1];
          if (preferredCamera) setSelectedCameraId(preferredCamera.deviceId);
        }
      } catch {
        if (!cancelled) {
          setPermissionError(
            "Camera access is unavailable. Allow camera permission or use the recovery field.",
          );
        }
      }
    };

    void start();
    return () => {
      cancelled = true;
      stop();
    };
  }, [onScan, scanning, stop, facingMode, selectedCameraId]);

  return {
    videoRef,
    permissionError,
    stop,
    cameras,
    selectedCameraId,
    selectCamera,
    cameraCount: cameras.length,
    switchLens,
  };
}
