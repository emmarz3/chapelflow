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
          { video: { facingMode: { ideal: "environment" } }, audio: false },
          videoRef.current,
          (result) => {
            const text = result?.getText().trim();
            if (!text || text === lastValue.current) return;
            lastValue.current = text;
            onScan(text);
          },
        );
        if (cancelled) controls.stop();
        else controlsRef.current = controls;
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
  }, [onScan, scanning, stop]);

  return { videoRef, permissionError, stop };
}
