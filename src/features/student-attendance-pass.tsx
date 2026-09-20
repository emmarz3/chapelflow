import { BrowserQRCodeReader, type IScannerControls } from "@zxing/browser";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Camera,
  CheckCircle2,
  Clipboard,
  QrCode,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import {
  Badge,
  Button,
  ErrorState,
  LoadingState,
  PageHeader,
} from "../components/ui";
import { attendanceService } from "../services/chapelflow";

export function StudentAttendancePassPage() {
  const video = useRef<HTMLVideoElement>(null);
  const controls = useRef<IScannerControls | null>(null);
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
      stopCamera();
      setMessage({
        tone: response.data.result === "recorded" ? "success" : "danger",
        text:
          response.message ||
          (response.data.result === "recorded"
            ? "Attendance recorded."
            : "Attendance already recorded."),
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
            <QrCode />
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
                ref={video}
                muted
                playsInline
                aria-label="Camera preview for usher QR scanner"
              />
            ) : (
              <div className="chapel-pass__unavailable">
                <Camera />
                <strong>Ready to scan</strong>
                <p>Point your camera at the usher's rotating QR code.</p>
              </div>
            )}
            <Button
              icon={<Camera />}
              onClick={() => void (scanning ? stopCamera() : startCamera())}
            >
              {scanning ? "Stop scanner" : "Open camera"}
            </Button>
          </div>
        </div>
        {message && (
          <p className={`form-note form-note--${message.tone}`}>
            <>{message.tone === "success" ? <CheckCircle2 /> : <XCircle />}</>{" "}
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
          <ShieldCheck />
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
            <QrCode />
            <h3>No attendance yet</h3>
            <p>Your completed chapel check-ins will appear here.</p>
          </div>
        )}
      </section>
    </div>
  );
}
