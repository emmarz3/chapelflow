import QRCode from "qrcode";
import { useQuery } from "@tanstack/react-query";
import { Clock3, LogOut, QrCode, RefreshCw, Wifi } from "lucide-react";
import { useEffect, useState } from "react";
import { Brand, Button, ErrorState, LoadingState } from "../components/ui";
import { attendanceService } from "../services/chapelflow";
import { useAuth } from "./auth-context";

export function UsherCheckpointQr({ compact = false, expectedSessionId }: { compact?: boolean; expectedSessionId?: string }) {
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
  }, [data?.token, data?.expires_at, refetch]);
  useEffect(() => {
    if (!data) return;
    let active = true;
    void QRCode.toDataURL(data.token, {
      width: 420,
      margin: 2,
      errorCorrectionLevel: "M",
    })
      .then((url) => { if (active) setImage(url); })
      .catch(() => { if (active) setImage(""); });
    return () => { active = false; };
  }, [data?.token]);

  if (isPending) return <LoadingState label="Preparing your secure attendance checkpoint" />;
  if (isError) return <ErrorState description={error.message} onRetry={() => void refetch()} />;
  if (expectedSessionId && data.session.id !== expectedSessionId)
    return <ErrorState description="The live checkpoint belongs to a different attendance session." onRetry={() => void refetch()} />;

  return (
    <section className={`usher-checkpoint__card${compact ? " usher-checkpoint__card--compact" : ""}`} aria-live="polite">
      <div className="usher-checkpoint__status"><Wifi /> Live checkpoint</div>
      <p className="eyebrow">{data.checkpoint_name}</p>
      <h2>{data.session.label || "Chapel service attendance"}</h2>
      {!compact && <p>Students scan this live code with ChapelFlow. It is unique to this checkpoint and expires automatically.</p>}
      <p><strong>{data.successful_scans}</strong> successful scans at this checkpoint</p>
      {data.session.window_closes_at && <p>Attendance window closes {new Date(data.session.window_closes_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}.</p>}
      <div className="usher-checkpoint__qr">
        {image ? <img src={image} alt="Live attendance QR code for students to scan" /> : <QrCode aria-hidden="true" />}
      </div>
      <strong className="usher-checkpoint__countdown"><Clock3 /> Refreshes in {secondsLeft}s</strong>
      <small>Token rotation: {data.rotation_seconds}s</small>
      {!compact && <Button variant="secondary" icon={<RefreshCw />} onClick={() => void refetch()}>Refresh now</Button>}
    </section>
  );
}

export function UsherAttendancePage() {
  const { logout } = useAuth();
  return (
    <main className="usher-checkpoint">
      <header className="usher-checkpoint__header">
        <Brand />
        <Button variant="secondary" icon={<LogOut />} onClick={() => void logout()}>Log out</Button>
      </header>
      <UsherCheckpointQr />
    </main>
  );
}
