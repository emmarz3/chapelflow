import QRCode from "qrcode";
import { useQuery } from "@tanstack/react-query";
import { Camera, Clock3, LogOut, QrCode, RefreshCw, Wifi } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Brand, Button, ErrorState, LoadingState } from "../components/ui";
import { queueOfflineQrScan, readPendingAttendance } from "../lib/offline-queue";
import { useQrScanner } from "../lib/use-qr-scanner";
import { attendanceService } from "../services/chapelflow";
import { useAuth } from "./auth-context";

export function UsherCheckpointQr({ compact = false, expectedSessionId }: { compact?: boolean; expectedSessionId?: string }) {
  const { user } = useAuth();
  const [now, setNow] = useState(Date.now());
  const [image, setImage] = useState("");
  const checkpoint = useQuery({
    queryKey: ["usher-checkpoint"],
    queryFn: async () => (await attendanceService.usherCheckpoint()).data,
    refetchInterval: false,
    refetchOnWindowFocus: true,
  });
  const { data, error, isError, isPending, refetch } = checkpoint;
  const expires = data ? new Date(data.expires_at).getTime() : 0;
  const secondsLeft = Math.max(0, Math.ceil((expires - now) / 1000));

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1_000);
    return () => window.clearInterval(timer);
  }, []);
  useEffect(() => {
    if (!data) return;
    const delay = Math.max(0, new Date(data.expires_at).getTime() - Date.now());
    const timer = window.setTimeout(() => void refetch(), delay);
    return () => window.clearTimeout(timer);
  }, [data, refetch]);
  useEffect(() => {
    if (!data) return;
    if (user && data.offline_grant) {
      window.sessionStorage.setItem(`chapelflow-offline-grant-${user.id}`, JSON.stringify({
        grant: data.offline_grant, sessionId: data.session.id,
        branchId: user.branchId,
        issuedAt: Date.now(),
      }));
    }
    let active = true;
    void QRCode.toDataURL(data.token, {
      width: 420,
      margin: 2,
      errorCorrectionLevel: "M",
    })
      .then((url) => { if (active) setImage(url); })
      .catch(() => { if (active) setImage(""); });
    return () => { active = false; };
  }, [data, user]);

  if (isPending) return <LoadingState label="Preparing your secure attendance checkpoint" />;
  if (isError) return <ErrorState description={error.message} onRetry={() => void refetch()} />;
  if (expectedSessionId && data.session.id !== expectedSessionId)
    return <ErrorState description="The live checkpoint belongs to a different attendance session." onRetry={() => void refetch()} />;

  return (
    <section className={`usher-checkpoint__card${compact ? " usher-checkpoint__card--compact" : ""}`} aria-live="polite">
      <div className="usher-checkpoint__status"><Wifi /> Live checkpoint</div>
      <p className="eyebrow">{data.checkpoint_name}</p>
      <h2>{data.session.label || "Chapel service attendance"}</h2>
      {!compact && <p>Students can scan the QR or enter its matching 6-digit code. Both are unique to this checkpoint and expire every 20 seconds.</p>}
      <p><strong>{data.successful_scans}</strong> successful scans at this checkpoint</p>
      {data.session.window_closes_at && <p>Attendance window closes {new Date(data.session.window_closes_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}.</p>}
      <div className="usher-checkpoint__qr">
        {image ? <img src={image} alt="Live attendance QR code for students to scan" /> : <QrCode aria-hidden="true" />}
      </div>
      <div className="usher-checkpoint__manual-code" aria-label="Camera-free attendance code">
        <small>Camera-free student code</small>
        <strong aria-live="polite" aria-atomic="true">{data.code}</strong>
        <span>Enter this 6-digit code in ChapelFlow. It rotates with the QR.</span>
      </div>
      <strong className="usher-checkpoint__countdown"><Clock3 /> Refreshes in {secondsLeft}s</strong>
      <small>Token rotation: {data.rotation_seconds}s</small>
      {!compact && <Button variant="secondary" icon={<RefreshCw />} onClick={() => void refetch()}>Refresh now</Button>}
    </section>
  );
}

export function UsherAttendancePage() {
  const { logout, user } = useAuth();
  const [scanning, setScanning] = useState(false);
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState(0);
  useEffect(() => {
    if (!user) return;
    const refresh = () => setPending(readPendingAttendance().filter((item) => item.method === "qr" && item.usherId === user.id).length);
    refresh();
    window.addEventListener("chapelflow:attendance-queue-changed", refresh);
    return () => window.removeEventListener("chapelflow:attendance-queue-changed", refresh);
  }, [user]);
  const onScan = useCallback(async (token: string) => {
    if (!user || !scanning) return;
    setScanning(false);
    const stored = window.sessionStorage.getItem(`chapelflow-offline-grant-${user.id}`);
    const grant = stored ? JSON.parse(stored) as { grant: string; sessionId: string; branchId: string; issuedAt: number } : null;
    if (!grant?.grant || !grant.sessionId || !grant.branchId || Date.now() - grant.issuedAt > 4 * 60 * 60 * 1000) {
      setMessage("Open this page while connected during an active service to prepare the offline scanner.");
      return;
    }
    if (!navigator.onLine) {
      const queued = queueOfflineQrScan({ token, grant: grant.grant, sessionId: grant.sessionId, branchId: grant.branchId, usherId: user.id });
      setMessage(queued ? "Identity QR saved. Reconnect with this usher account to synchronize." : "This identity QR is already queued for this service.");
      return;
    }
    try {
      await attendanceService.qrCheckIn({ token, sessionId: grant.sessionId });
      setMessage("Student attendance recorded.");
    } catch (error) {
      if (!navigator.onLine) {
        queueOfflineQrScan({ token, grant: grant.grant, sessionId: grant.sessionId, branchId: grant.branchId, usherId: user.id });
        setMessage("Connection lost. Identity QR saved for synchronization.");
      } else setMessage(error instanceof Error ? error.message : "Check-in failed.");
    }
  }, [scanning, user]);
  const { videoRef, permissionError } = useQrScanner((token) => { void onScan(token); }, scanning);
  return (
    <main className="usher-checkpoint">
      <header className="usher-checkpoint__header">
        <Brand />
        <Button variant="secondary" icon={<LogOut />} onClick={() => void logout()}>Log out</Button>
      </header>
      <UsherCheckpointQr />
      <section className="usher-checkpoint__card" aria-live="polite">
        <h2>Scan a student identity pass</h2>
        <p>Open this page online during the service. If the connection drops, scan students' personal ChapelFlow QR codes here and keep this tab open until they synchronize.</p>
        <p>{pending} scan{pending === 1 ? "" : "s"} awaiting synchronization on this device.</p>
        {scanning && <video ref={videoRef} muted playsInline aria-label="Student identity QR scanner camera" className="kiosk__camera" />}
        {permissionError && <p role="alert">{permissionError}</p>}
        {message && <p role="status">{message}</p>}
        <Button icon={<Camera />} onClick={() => { setMessage(""); setScanning((value) => !value); }}>
          {scanning ? "Stop scanner" : "Scan identity QR"}
        </Button>
      </section>
    </main>
  );
}
