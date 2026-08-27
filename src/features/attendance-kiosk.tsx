import {
  Camera,
  CheckCircle2,
  Clock3,
  Keyboard,
  LockKeyhole,
  QrCode,
  RotateCcw,
  WifiOff,
  XCircle,
} from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Brand, Button } from "../components/ui";
import { attendanceService } from "../services/chapelflow";
import { queueAttendanceCheckIn } from "../lib/offline-queue";

type KioskState =
  "idle" | "camera" | "submitting" | "success" | "error" | "offline";

export function AttendanceKioskPage() {
  const [state, setState] = useState<KioskState>("idle");
  const [message, setMessage] = useState("");
  const [manual, setManual] = useState(false);
  const video = useRef<HTMLVideoElement>(null);
  const stream = useRef<MediaStream | null>(null);
  const timeout = useRef<number | undefined>(undefined);
  function reset() {
    stream.current?.getTracks().forEach((track) => track.stop());
    stream.current = null;
    setState("idle");
    setManual(false);
    setMessage("");
    window.clearTimeout(timeout.current);
  }
  function scheduleReset(delay = 5000) {
    window.clearTimeout(timeout.current);
    timeout.current = window.setTimeout(reset, delay);
  }
  useEffect(
    () => () => {
      stream.current?.getTracks().forEach((track) => track.stop());
      window.clearTimeout(timeout.current);
    },
    [],
  );
  async function openCamera() {
    setState("camera");
    setMessage("");
    try {
      const media = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment" },
        audio: false,
      });
      stream.current = media;
      if (video.current) {
        video.current.srcObject = media;
        await video.current.play();
      }
    } catch {
      setState("error");
      setMessage(
        "Camera access was not granted. Use manual entry or review browser permissions.",
      );
    }
  }
  async function submit(identifier: string) {
    setState("submitting");
    try {
      if (!navigator.onLine) {
        const queued = queueAttendanceCheckIn({
          sessionId: "current",
          memberIdentifier: identifier,
          method: "kiosk",
        });
        setState(queued ? "offline" : "error");
        setMessage(
          queued
            ? "Check-in saved securely on this device for synchronization."
            : "This check-in is already waiting to synchronize.",
        );
        scheduleReset();
        return;
      }
      await attendanceService.checkIn("current", {
        memberIdentifier: identifier,
        method: "kiosk",
      });
      setState("success");
      setMessage("Attendance confirmed. You may step away from the kiosk.");
      scheduleReset();
    } catch (error) {
      setState("error");
      setMessage(
        error instanceof Error
          ? error.message
          : "The check-in could not be completed.",
      );
      scheduleReset(8000);
    }
  }
  function manualSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const identifier = String(
      new FormData(event.currentTarget).get("identifier"),
    ).trim();
    if (identifier) void submit(identifier);
  }
  return (
    <main className="kiosk">
      <header>
        <Brand inverse />
        <div>
          <LockKeyhole /> Kiosk mode · administrative navigation disabled
        </div>
        <Link to="/app/attendance">Exit kiosk</Link>
      </header>
      <section className="kiosk__content" aria-live="polite">
        {state === "idle" && (
          <>
            <span className="kiosk__icon">
              <QrCode />
            </span>
            <p className="eyebrow">Sunday Worship Service</p>
            <h1>Check in to chapel</h1>
            <p>
              Use your ChapelFlow QR code or enter your matric number. This
              screen clears automatically after every check-in.
            </p>
            <div className="kiosk__buttons">
              <Button onClick={() => void openCamera()} icon={<Camera />}>
                Scan QR code
              </Button>
              <Button
                variant="secondary"
                onClick={() => setManual(true)}
                icon={<Keyboard />}
              >
                Enter identifier
              </Button>
            </div>
            {manual && (
              <form className="kiosk__manual" onSubmit={manualSubmit}>
                <label>
                  Matric number or member ID
                  <input
                    name="identifier"
                    autoFocus
                    autoComplete="off"
                    required
                  />
                </label>
                <Button type="submit">Check in</Button>
              </form>
            )}
          </>
        )}
        {state === "camera" && (
          <>
            <div className="kiosk__camera">
              <video
                ref={video}
                muted
                playsInline
                aria-label="QR scanner camera preview"
              />
              <span>
                <i />
                <i />
                <i />
                <i />
              </span>
            </div>
            <h1>Hold your QR code inside the frame</h1>
            <p>If scanning is unavailable, return and use your identifier.</p>
            <Button variant="secondary" onClick={reset}>
              Cancel scan
            </Button>
          </>
        )}
        {state === "submitting" && (
          <>
            <span className="kiosk__icon kiosk__icon--loading">
              <RotateCcw />
            </span>
            <h1>Checking you in…</h1>
            <p>Please wait. Do not submit the same code again.</p>
          </>
        )}
        {state === "success" && (
          <>
            <span className="kiosk__icon kiosk__icon--success">
              <CheckCircle2 />
            </span>
            <h1>Check-in confirmed</h1>
            <p>{message}</p>
            <small>
              <Clock3 /> This screen will reset automatically.
            </small>
          </>
        )}
        {state === "offline" && (
          <>
            <span className="kiosk__icon kiosk__icon--warning">
              <WifiOff />
            </span>
            <h1>Saved for synchronization</h1>
            <p>{message}</p>
            <small>
              The backend will check for duplicates before accepting the record.
            </small>
          </>
        )}
        {state === "error" && (
          <>
            <span className="kiosk__icon kiosk__icon--danger">
              <XCircle />
            </span>
            <h1>Check-in not completed</h1>
            <p>{message}</p>
            <Button variant="secondary" onClick={reset}>
              Try again
            </Button>
          </>
        )}
      </section>
      <footer>
        Your details appear only long enough to confirm attendance. Do not leave
        personal information on this device.
      </footer>
    </main>
  );
}
