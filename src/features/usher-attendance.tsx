import QRCode from "qrcode";
import { useQuery } from "@tanstack/react-query";
import { Clock3, LogOut, QrCode, RefreshCw, Wifi } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Brand, Button, ErrorState, LoadingState } from "../components/ui";
import { attendanceService } from "../services/chapelflow";
import { useAuth } from "./auth-context";

export function UsherAttendancePage() {
  const { logout } = useAuth();
  const [now, setNow] = useState(Date.now());
  const [image, setImage] = useState("");
  const checkpoint = useQuery({
    queryKey: ["usher-checkpoint"],
    queryFn: async () => (await attendanceService.usherCheckpoint()).data,
    refetchInterval: 15_000,
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
    if (secondsLeft === 0 && data) void refetch();
  }, [secondsLeft, data, refetch]);
  useEffect(() => {
    if (!data) return;
    void QRCode.toDataURL(data.token, {
      width: 420,
      margin: 2,
      errorCorrectionLevel: "M",
    })
      .then(setImage)
      .catch(() => setImage(""));
  }, [data]);

  const countdown = useMemo(
    () => `${String(secondsLeft).padStart(2, "0")} seconds`,
    [secondsLeft],
  );
  if (isPending)
    return <LoadingState label="Preparing your secure attendance checkpoint" />;
  if (isError)
    return (
      <ErrorState description={error.message} onRetry={() => void refetch()} />
    );
  return (
    <main className="usher-checkpoint" aria-live="polite">
      <header className="usher-checkpoint__header">
        <Brand />
        <Button
          variant="secondary"
          icon={<LogOut />}
          onClick={() => void logout()}
        >
          Log out
        </Button>
      </header>
      <section className="usher-checkpoint__card">
        <div className="usher-checkpoint__status">
          <Wifi /> Live checkpoint
        </div>
        <p className="eyebrow">{data.checkpoint_name}</p>
        <h1>{data.session.label || "Chapel service attendance"}</h1>
        <p>
          Students scan this live code with ChapelFlow. It is unique to this
          checkpoint and expires automatically.
        </p>
        <p><strong>{data.successful_scans}</strong> successful scans at this checkpoint</p>
        {data.session.window_closes_at && <p>Attendance window closes {new Date(data.session.window_closes_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}.</p>}
        <div className="usher-checkpoint__qr">
          {image ? (
            <img
              src={image}
              alt="Live attendance QR code for students to scan"
            />
          ) : (
            <QrCode aria-hidden="true" />
          )}
        </div>
        <strong className="usher-checkpoint__countdown">
          <Clock3 /> Refreshing in {countdown}
        </strong>
        <Button
          variant="secondary"
          icon={<RefreshCw />}
          onClick={() => void refetch()}
        >
          Refresh now
        </Button>
      </section>
    </main>
  );
}
