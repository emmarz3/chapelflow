import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Camera,
  CheckCircle2,
  Clipboard,
  QrCode,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  Badge,
  Button,
  ErrorState,
  LoadingState,
  PageHeader,
} from "../components/ui";
import { useQrScanner } from "../lib/use-qr-scanner";
import { attendanceService } from "../services/chapelflow";

export function StudentAttendancePassPage() {
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
      setScanning(false);
      setMessage({
        tone: response.data.result === "recorded" ? "success" : "danger",
        text:
          response.data.result === "duplicate"
            ? "Attendance has already been recorded for this session."
            : response.message || "Attendance recorded.",
      });
      void history.refetch();
    },
    onError: (error) => {
      setScanning(false);
      setMessage({
        tone: "danger",
        text:
          error instanceof Error
            ? error.message
            : "Attendance could not be recorded.",
      });
    },
  });
  const submitCode = useMutation({
    mutationFn: ({ sessionId, code }: { sessionId: string; code: string }) =>
      attendanceService.studentCode(sessionId, code),
    onSuccess: (response) => {
      setManualToken("");
      setMessage({
        tone: response.data.result === "recorded" ? "success" : "danger",
        text: response.message || (response.data.result === "recorded" ? "Attendance recorded." : "Attendance has already been recorded for this session."),
      });
      void history.refetch();
    },
    onError: (error) => {
      setMessage({ tone: "danger", text: navigator.onLine
        ? error instanceof Error ? error.message : "Attendance could not be recorded."
        : "Connect to the internet and enter the usher's current code. Ask the usher to record you if you are offline." });
    },
  });
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
        description="Scan the live usher QR or enter its rotating 6-digit code if your camera is unavailable."
      />
      <section className="chapel-pass">
        {message?.tone === "success" && (
          <div className="modal-backdrop" role="presentation">
            <section className="modal attendance-success" role="alertdialog" aria-modal="true" aria-labelledby="attendance-success-title">
              <CheckCircle2 aria-hidden="true" />
              <h2 id="attendance-success-title">{message.text.includes("saved on this device") ? "Attendance saved offline" : "Attendance successfully recorded"}</h2>
              <p>{message.text}</p>
              <Button onClick={() => setMessage(null)}>Done</Button>
            </section>
          </div>
        )}
        <header>
          <div className="chapel-pass__mark">
            <QrCode aria-hidden="true" />
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
              <div className="chapel-pass__camera">
                <video
                  ref={videoRef}
                  muted
                  playsInline
                  aria-label="Camera preview for usher QR scanner"
                />
                <div className="chapel-pass__aim" aria-hidden="true">
                  <span className="chapel-pass__aim-frame" />
                  <span className="chapel-pass__aim-hint">Align QR inside frame</span>
                </div>
              </div>
            ) : (
              <div className="chapel-pass__unavailable">
                <Camera aria-hidden="true" />
                <strong>Ready to scan</strong>
                <p>Open the camera and fit the usher’s full QR code inside the guide. You can also enter its rotating code below.</p>
              </div>
            )}
            <Button
              icon={<Camera />}
              onClick={() => {
                setMessage(null);
                setScanning((value) => !value);
              }}
            >
              {scanning ? "Stop scanner" : "Open camera"}
            </Button>
          </div>
        </div>
        {message && (
          <p
            className={`form-note form-note--${message.tone}`}
            role="status"
            aria-live="polite"
          >
            <>{message.tone === "success" ? <CheckCircle2 aria-hidden="true" /> : <XCircle aria-hidden="true" />}</>{" "}
            {message.text}
          </p>
        )}
        <form
          className="chapel-pass__recovery"
          onSubmit={(event) => {
            event.preventDefault();
            const code = manualToken.trim();
            const sessionId = pass.data.session?.id;
            if (!/^\d{6}$/.test(code) || !sessionId) {
              setMessage({ tone: "danger", text: sessionId ? "Enter the 6-digit code shown by your usher." : "There is no open attendance session." });
              return;
            }
            setMessage(null);
            if (!navigator.onLine) {
              setMessage({ tone: "danger", text: "Connect to the internet and enter the usher's current code. Ask the usher to record you if you are offline." });
              return;
            }
            submitCode.mutate({ sessionId, code });
          }}
        >
          <div className="chapel-pass__recovery-heading">
            <strong>Can’t scan the QR?</strong>
            <span>Enter the 6-digit code displayed by the usher. It refreshes every 20 seconds.</span>
          </div>
          <label>
            Usher attendance code
            <input
              value={manualToken}
              onChange={(event) => setManualToken(event.target.value.replace(/\D/g, "").slice(0, 6))}
              placeholder="000000"
              inputMode="numeric"
              pattern="[0-9]{6}"
              maxLength={6}
              autoComplete="off"
              aria-label="6-digit usher attendance code"
            />
          </label>
          <Button
            variant="secondary"
            icon={<Clipboard />}
            type="submit"
            disabled={scan.isPending || submitCode.isPending || manualToken.length !== 6 || !pass.data.session}
          >
            Submit code
          </Button>
        </form>
        <footer>
          <ShieldCheck aria-hidden="true" />
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
            <QrCode aria-hidden="true" />
            <h3>No attendance yet</h3>
            <p>Your completed chapel check-ins will appear here.</p>
          </div>
        )}
      </section>
    </div>
  );
}
