import { BrowserQRCodeReader, type IScannerControls } from "@zxing/browser";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Camera,
  CheckCircle2,
  Clock3,
  Flashlight,
  Keyboard,
  LogOut,
  RefreshCw,
  ScanLine,
  ShieldAlert,
  SwitchCamera,
  XCircle,
} from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { ApiError } from "../lib/api";
import { Brand, Button } from "../components/ui";
import { useFeatureMotion } from "../components/motion/motion-system";
import { attendanceService } from "../services/chapelflow";
import type { AttendanceScanResult } from "../types/domain";
import { useAuth } from "./auth-context";

type ScannerState =
  "idle" | "starting" | "ready" | "submitting" | "camera-error";

export function UsherAttendancePage() {
  const { user, logout } = useAuth();
  const client = useQueryClient();
  const videoRef = useRef<HTMLVideoElement>(null);
  const pageRef = useRef<HTMLElement>(null);
  const controlsRef = useRef<IScannerControls | null>(null);
  const processingRef = useRef(false);
  const lastTokenRef = useRef({ value: "", at: 0 });
  const [scannerState, setScannerState] = useState<ScannerState>("idle");
  const [cameraMessage, setCameraMessage] = useState("");
  const [manualOpen, setManualOpen] = useState(false);
  const [torchAvailable, setTorchAvailable] = useState(false);
  const [torchOn, setTorchOn] = useState(false);
  const [result, setResult] = useState<AttendanceScanResult | null>(null);
  const [resultError, setResultError] = useState<{
    title: string;
    message: string;
  } | null>(null);

  const active = useQuery({
    queryKey: ["usher-attendance", "active"],
    queryFn: async () => (await attendanceService.activeScannerSession()).data,
    refetchInterval: 10_000,
  });
  useFeatureMotion(pageRef, active.data?.session.id ?? active.status);

  function stopCamera() {
    controlsRef.current?.stop();
    controlsRef.current = null;
    processingRef.current = false;
    setTorchAvailable(false);
    setTorchOn(false);
    setScannerState("idle");
  }

  useEffect(() => stopCamera, []);
  useEffect(() => {
    if (!active.data) stopCamera();
  }, [active.data]);

  function presentError(error: unknown) {
    const code = error instanceof ApiError ? error.code : "UNKNOWN";
    const messages: Record<string, { title: string; message: string }> = {
      INVALID_PASS: {
        title: "Invalid ChapelFlow pass",
        message: "This QR code could not be verified.",
      },
      STUDENT_INACTIVE: {
        title: "Attendance not recorded",
        message: "This student account is inactive. Contact an administrator.",
      },
      NO_ACTIVE_SESSION: {
        title: "No active attendance session",
        message: "Attendance has closed or is not currently open.",
      },
      NETWORK_ERROR: {
        title: "Connection problem",
        message:
          "Attendance was not recorded. Check the connection and scan again.",
      },
    };
    setResult(null);
    setResultError(
      messages[code] ?? {
        title: "Attendance not recorded",
        message:
          error instanceof Error
            ? error.message
            : "The scan could not be completed.",
      },
    );
    window.setTimeout(() => setResultError(null), 3_500);
  }

  const scan = useMutation({
    mutationFn: (token: string) =>
      attendanceService.scan({
        token,
        sessionId: active.data!.session.id,
        idempotencyKey: crypto.randomUUID(),
      }),
    onSuccess: (response) => {
      setResultError(null);
      setResult(response.data);
      if (response.data.result === "recorded" && navigator.vibrate)
        navigator.vibrate(80);
      void client.invalidateQueries({ queryKey: ["usher-attendance"] });
      window.setTimeout(() => setResult(null), 3_000);
    },
    onError: presentError,
    onSettled: () => {
      processingRef.current = false;
      setScannerState(controlsRef.current ? "ready" : "idle");
    },
  });

  const manual = useMutation({
    mutationFn: (values: { identifier: string; reason: string }) =>
      attendanceService.manual({
        ...values,
        sessionId: active.data!.session.id,
        idempotencyKey: crypto.randomUUID(),
      }),
    onSuccess: (response) => {
      setManualOpen(false);
      setResult(response.data);
      void client.invalidateQueries({ queryKey: ["usher-attendance"] });
      window.setTimeout(() => setResult(null), 3_000);
    },
    onError: presentError,
  });

  async function startCamera(deviceId?: string) {
    if (!active.data || !videoRef.current) return;
    stopCamera();
    setScannerState("starting");
    setCameraMessage("");
    try {
      const reader = new BrowserQRCodeReader(undefined, {
        delayBetweenScanAttempts: 150,
      });
      const controls = await reader.decodeFromConstraints(
        {
          video: deviceId
            ? { deviceId: { exact: deviceId } }
            : { facingMode: { ideal: "environment" } },
          audio: false,
        },
        videoRef.current,
        (decoded) => {
          if (!decoded || processingRef.current) return;
          const token = decoded.getText();
          const now = Date.now();
          if (
            lastTokenRef.current.value === token &&
            now - lastTokenRef.current.at < 4_000
          )
            return;
          lastTokenRef.current = { value: token, at: now };
          processingRef.current = true;
          setScannerState("submitting");
          scan.mutate(token);
        },
      );
      controlsRef.current = controls;
      setTorchAvailable(Boolean(controls.switchTorch));
      setScannerState("ready");
    } catch {
      setScannerState("camera-error");
      setCameraMessage(
        "Camera access is unavailable. Check browser permissions or use manual lookup.",
      );
    }
  }

  async function switchCamera() {
    try {
      const devices = await BrowserQRCodeReader.listVideoInputDevices();
      if (devices.length < 2) return;
      const current = videoRef.current?.srcObject as MediaStream | null;
      const currentId = current?.getVideoTracks()[0]?.getSettings().deviceId;
      const index = devices.findIndex(
        (device) => device.deviceId === currentId,
      );
      await startCamera(devices[(index + 1) % devices.length]?.deviceId);
    } catch {
      setCameraMessage("Another camera could not be opened.");
    }
  }

  async function toggleTorch() {
    if (!controlsRef.current?.switchTorch) return;
    try {
      await controlsRef.current.switchTorch(!torchOn);
      setTorchOn((value) => !value);
    } catch {
      setCameraMessage("The camera torch could not be changed on this device.");
    }
  }

  function submitManual(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    manual.mutate({
      identifier: String(data.get("identifier")).trim(),
      reason: String(data.get("reason")).trim(),
    });
  }

  return (
    <main className="usher-scanner" ref={pageRef}>
      <header className="usher-scanner__header">
        <Brand inverse />
        <div>
          <strong>{user?.name}</strong>
          <small>Attendance usher</small>
        </div>
        <Button variant="ghost" icon={<LogOut />} onClick={() => void logout()}>
          Sign out
        </Button>
      </header>
      <section className="usher-scanner__content">
        {active.isPending ? (
          <div className="usher-scanner__notice">
            <RefreshCw className="spin" />
            <h1>Loading active service</h1>
          </div>
        ) : active.isError ? (
          <div className="usher-scanner__notice usher-scanner__notice--error">
            <XCircle />
            <h1>Could not load attendance</h1>
            <p>{active.error.message}</p>
            <Button onClick={() => void active.refetch()}>Try again</Button>
          </div>
        ) : !active.data ? (
          <div className="usher-scanner__notice">
            <Clock3 />
            <h1>No active attendance session</h1>
            <p>
              An administrator must activate a chapel service before scanning
              can begin.
            </p>
          </div>
        ) : (
          <>
            <div className="usher-session-bar">
              <div>
                <span className="live-pulse" />
                <div>
                  <small>Active service</small>
                  <strong>{active.data.session.title}</strong>
                </div>
              </div>
              <div>
                <strong>{active.data.session.count}</strong>
                <small>Students scanned</small>
              </div>
            </div>
            <div className="usher-scanner__grid">
              <section className="scanner-panel">
                <div
                  className="scanner-camera"
                  data-scanning={
                    scannerState === "ready" || scannerState === "submitting"
                  }
                >
                  <video
                    ref={videoRef}
                    muted
                    playsInline
                    aria-label="Attendance QR scanner camera"
                  />
                  <span className="scanner-frame">
                    <i />
                    <i />
                    <i />
                    <i />
                  </span>
                  {scannerState === "idle" && (
                    <div className="scanner-overlay">
                      <ScanLine />
                      <strong>Scanner paused</strong>
                    </div>
                  )}
                  {scannerState === "starting" && (
                    <div className="scanner-overlay">
                      <RefreshCw className="spin" />
                      <strong>Starting camera</strong>
                    </div>
                  )}
                </div>
                <div className="scanner-actions">
                  {scannerState === "idle" ||
                  scannerState === "camera-error" ? (
                    <Button
                      icon={<Camera />}
                      onClick={() => void startCamera()}
                    >
                      Start scanner
                    </Button>
                  ) : (
                    <Button variant="secondary" onClick={stopCamera}>
                      Pause scanner
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    icon={<SwitchCamera />}
                    onClick={() => void switchCamera()}
                    disabled={!controlsRef.current}
                  >
                    Switch camera
                  </Button>
                  {torchAvailable && (
                    <Button
                      variant="ghost"
                      icon={<Flashlight />}
                      onClick={() => void toggleTorch()}
                    >
                      {torchOn ? "Torch off" : "Torch on"}
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    icon={<Keyboard />}
                    onClick={() => setManualOpen((value) => !value)}
                  >
                    Manual lookup
                  </Button>
                </div>
                {cameraMessage && (
                  <div className="form-error" role="alert">
                    {cameraMessage}
                  </div>
                )}
                {manualOpen && (
                  <form className="scanner-manual" onSubmit={submitManual}>
                    <label>
                      Matric number
                      <input name="identifier" autoComplete="off" required />
                    </label>
                    <label>
                      Reason
                      <textarea name="reason" minLength={3} required />
                    </label>
                    <Button type="submit" loading={manual.isPending}>
                      Confirm manual attendance
                    </Button>
                  </form>
                )}
              </section>
              <aside className="scanner-activity">
                <h2>Recent scans</h2>
                {active.data.recent.length ? (
                  active.data.recent.slice(0, 8).map((record) => (
                    <article key={record.id}>
                      <CheckCircle2 />
                      <div>
                        <strong>{record.memberName}</strong>
                        <small>
                          {record.identifier} ·{" "}
                          {new Date(record.time).toLocaleTimeString()}
                        </small>
                      </div>
                    </article>
                  ))
                ) : (
                  <p>No students scanned by this usher yet.</p>
                )}
              </aside>
            </div>
          </>
        )}
      </section>
      {(result || resultError) && (
        <div
          className={`scan-result ${result?.result === "recorded" ? "scan-result--success" : result?.result === "duplicate" ? "scan-result--duplicate" : "scan-result--error"}`}
          role="status"
          aria-live="assertive"
        >
          {result?.result === "recorded" ? <CheckCircle2 /> : <ShieldAlert />}
          <div>
            <small>
              {result?.result === "recorded"
                ? "Attendance recorded"
                : result?.result === "duplicate"
                  ? "Already recorded"
                  : resultError?.title}
            </small>
            {result ? (
              <>
                <h2>{result.record.student.name}</h2>
                <p>
                  {result.record.student.identifier} ·{" "}
                  {new Date(result.record.recordedAt).toLocaleTimeString()}
                </p>
              </>
            ) : (
              <p>{resultError?.message}</p>
            )}
          </div>
        </div>
      )}
    </main>
  );
}
