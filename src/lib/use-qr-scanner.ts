import { BrowserQRCodeReader, type IScannerControls } from "@zxing/browser";
import { useCallback, useEffect, useRef, useState } from "react";

const MATRIC_PATTERN = /^[A-Za-z]{2,6}\/[0-9]{2,4}\/[0-9]{3,6}$/;

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
  const [cameraCount, setCameraCount] = useState(0);

  const stop = useCallback(() => {
    controlsRef.current?.stop();
    controlsRef.current = null;
    lastValue.current = "";
  }, []);

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
        const controls = await reader.decodeFromConstraints(
          { video: { facingMode: { ideal: facingMode } }, audio: false },
          videoRef.current,
          (result) => {
            const text = result?.getText().trim();
            if (!text || text === lastValue.current) return;
            lastValue.current = text;
            onScan(text);
          },
        );
        if (cancelled) controls.stop();
        else {
          controlsRef.current = controls;
          void navigator.mediaDevices.enumerateDevices().then((devices) => {
            if (!cancelled) setCameraCount(devices.filter((device) => device.kind === "videoinput").length);
          }).catch(() => {});
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
  }, [onScan, scanning, stop, facingMode]);

  return { videoRef, permissionError, stop, cameraCount, switchLens: () => setFacingMode((current) => current === "environment" ? "user" : "environment") };
}
