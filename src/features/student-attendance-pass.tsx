<<<<<<< HEAD
=======
import { BrowserQRCodeReader, type IScannerControls } from "@zxing/browser";
>>>>>>> origin/main
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Camera,
  CheckCircle2,
  Clipboard,
  QrCode,
  ShieldCheck,
  XCircle,
} from "lucide-react";
<<<<<<< HEAD
import { useCallback, useEffect, useRef, useState } from "react";
=======
import { useEffect, useRef, useState } from "react";
>>>>>>> origin/main
import {
  Badge,
  Button,
  ErrorState,
  LoadingState,
  PageHeader,
} from "../components/ui";
<<<<<<< HEAD
import { useQrScanner } from "../lib/use-qr-scanner";
import { attendanceService } from "../services/chapelflow";

export function StudentAttendancePassPage() {
=======
import { attendanceService } from "../services/chapelflow";

export function StudentAttendancePassPage() {
  const video = useRef<HTMLVideoElement>(null);
  const controls = useRef<IScannerControls | null>(null);
>>>>>>> origin/main
  const [scanning, setScanning] = useState(false);
  const [manualToken, setManualToken] = useState("");
  const [message, setMessage] = useState<{
    tone: "success" | "danger";
    text: string;
  } | null>(null);
  const pass = useQuery({
    queryKey: ["attendance-pass"],
    queryFn: async () => (await attendanceService.pass()).data,
  });
  const history = useQuery({
    queryKey: ["attendance-history", "me"],
    queryFn: async () => (await attendanceService.history()).data,
  });
  const scan = useMutation({
    mutationFn: attendanceService.studentScan,
    onSuccess: (response) => {
<<<<<<< HEAD
      setScanning(false);
=======
      stopCamera();
>>>>>>> origin/main
      setMessage({
        tone: response.data.result === "recorded" ? "success" : "danger",
        text:
          response.data.result === "duplicate"
            ? "Attendance has already been recorded for this session."
            : response.message || "Attendance recorded.",
      });
      void history.refetch();
    },
    onError: (error) =>
      setMessage({
        tone: "danger",
        text:
          error instanceof Error
            ? error.message
            : "Attendance could not be recorded.",
      }),
  });
<<<<<<< HEAD
  const pendingScan = useRef(false);
  pendingScan.current = scan.isPending;
  const mutateScan = scan.mutate;
  const onScan = useCallback(
    (text: string) => {
      if (!pendingScan.current) mutateScan(text);
    },
    [mutateScan],
  );
  const { videoRef, permissionError } = useQrScanner(onScan, scanning);
  useEffect(() => {
    if (!permissionError) return;
    setScanning(false);
    setMessage({ tone: "danger", text: permissionError });
  }, [permissionError]);
=======
  function stopCamera() {
    controls.current?.stop();
    controls.current = null;
    setScanning(false);
  }
  useEffect(() => () => controls.current?.stop(), []);
  async function startCamera() {
    setMessage(null);
    setScanning(true);
    await new Promise<void>((resolve) =>
      window.requestAnimationFrame(() => resolve()),
    );
    if (!video.current) {
      setScanning(false);
      return;
    }
    try {
      const reader = new BrowserQRCodeReader();
      controls.current = await reader.decodeFromConstraints(
        { video: { facingMode: { ideal: "environment" } }, audio: false },
        video.current,
        (result) => {
          if (result && !scan.isPending) scan.mutate(result.getText());
        },
      );
    } catch {
      setScanning(false);
      setMessage({
        tone: "danger",
        text: "Camera access is unavailable. Allow camera permission or use the secure recovery field.",
      });
    }
  }
>>>>>>> origin/main
  if (pass.isPending)
    return <LoadingState label="Loading your attendance scanner" />;
  if (pass.isError)
    return (
      <ErrorState
        description={pass.error.message}
        onRetry={() => void pass.refetch()}
      />
    );
  return (
    <div className="motion-feature motion-feature--pass">
      <PageHeader
        eyebrow="Student attendance"
        title="My Chapel Pass"
        description="Attendance is recorded only when you scan a live QR shown by an authorized usher."
      />
      <section className="chapel-pass">
        <header>
          <div className="chapel-pass__mark">
<<<<<<< HEAD
            <QrCode aria-hidden="true" />
=======
            <QrCode />
>>>>>>> origin/main
          </div>
          <div>
            <small>Chrisland University Chapel</small>
            <h2>Scan the usher QR</h2>
          </div>
          <Badge
            tone={pass.data.passStatus === "active" ? "success" : "danger"}
          >
            {pass.data.passStatus}
          </Badge>
        </header>
        <div className="chapel-pass__body">
          <div className="chapel-pass__identity">
            <span className="profile-summary__avatar">
              {pass.data.student.name
                .split(/\s+/)
                .slice(0, 2)
                .map((part) => part[0])
                .join("")}
            </span>
            <h3>{pass.data.student.name}</h3>
            <strong>{pass.data.student.identifier}</strong>
            <p>{pass.data.student.programme || "Student account"}</p>
          </div>
          <div className="chapel-pass__qr">
            {scanning ? (
              <video
<<<<<<< HEAD
                ref={videoRef}
=======
                ref={video}
>>>>>>> origin/main
                muted
                playsInline
                aria-label="Camera preview for usher QR scanner"
              />
            ) : (
              <div className="chapel-pass__unavailable">
<<<<<<< HEAD
                <Camera aria-hidden="true" />
=======
                <Camera />
>>>>>>> origin/main
                <strong>Ready to scan</strong>
                <p>Point your camera at the usher's rotating QR code.</p>
              </div>
            )}
            <Button
              icon={<Camera />}
<<<<<<< HEAD
              onClick={() => {
                setMessage(null);
                setScanning((value) => !value);
              }}
=======
              onClick={() => void (scanning ? stopCamera() : startCamera())}
>>>>>>> origin/main
            >
              {scanning ? "Stop scanner" : "Open camera"}
            </Button>
          </div>
        </div>
        {message && (
<<<<<<< HEAD
          <p
            className={`form-note form-note--${message.tone}`}
            role="status"
            aria-live="polite"
          >
            <>{message.tone === "success" ? <CheckCircle2 aria-hidden="true" /> : <XCircle aria-hidden="true" />}</>{" "}
=======
          <p className={`form-note form-note--${message.tone}`}>
            <>{message.tone === "success" ? <CheckCircle2 /> : <XCircle />}</>{" "}
>>>>>>> origin/main
            {message.text}
          </p>
        )}
        <form
          className="chapel-pass__recovery"
          onSubmit={(event) => {
            event.preventDefault();
            if (manualToken.trim()) scan.mutate(manualToken.trim());
          }}
        >
          <label>
            Secure recovery token
            <input
              value={manualToken}
              onChange={(event) => setManualToken(event.target.value)}
              placeholder="Paste a live usher QR token"
              autoComplete="off"
            />
          </label>
          <Button
            variant="secondary"
            icon={<Clipboard />}
            type="submit"
            disabled={scan.isPending}
          >
            Submit token
          </Button>
        </form>
        <footer>
<<<<<<< HEAD
          <ShieldCheck aria-hidden="true" />
=======
          <ShieldCheck />
>>>>>>> origin/main
          <span>
            Your permanent personal QR code cannot be used to self-record
            attendance.
          </span>
        </footer>
      </section>
      <section className="table-panel attendance-history">
        <header>
          <div className="panel-heading">
            <div>
              <h2>Your attendance history</h2>
              <p>Only records linked to your account are shown.</p>
            </div>
          </div>
        </header>
        {history.isPending ? (
          <LoadingState label="Loading attendance history" />
        ) : history.isError ? (
          <ErrorState
            description={history.error.message}
            onRetry={() => void history.refetch()}
          />
        ) : history.data.length ? (
          <table>
            <thead>
              <tr>
                <th>Service</th>
                <th>Date</th>
                <th>Recorded</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {history.data.map((record) => (
                <tr key={`${record.title}-${record.recorded_at}`}>
                  <td>
                    <strong>{record.title}</strong>
                  </td>
                  <td>{new Date(record.date).toLocaleDateString()}</td>
                  <td>{new Date(record.recorded_at).toLocaleTimeString()}</td>
                  <td>
                    <Badge tone="success">{record.status}</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="empty-state">
<<<<<<< HEAD
            <QrCode aria-hidden="true" />
=======
            <QrCode />
>>>>>>> origin/main
            <h3>No attendance yet</h3>
            <p>Your completed chapel check-ins will appear here.</p>
          </div>
        )}
      </section>
    </div>
  );
}
