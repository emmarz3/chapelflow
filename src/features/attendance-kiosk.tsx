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
<<<<<<< HEAD
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
=======
import { useEffect, useRef, useState, type FormEvent } from "react";
>>>>>>> origin/main
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Brand, Button } from "../components/ui";
import { useFeatureMotion } from "../components/motion/motion-system";
import { attendanceService } from "../services/chapelflow";
import { queueAttendanceCheckIn } from "../lib/offline-queue";
<<<<<<< HEAD
import { classifyKioskScan, useQrScanner } from "../lib/use-qr-scanner";
=======
>>>>>>> origin/main
import { useAuth } from "./auth-context";

type KioskState =
  "idle" | "camera" | "submitting" | "success" | "error" | "offline";

export function AttendanceKioskPage() {
  const { user } = useAuth();
  const currentSession = useQuery({
    queryKey: ["attendance", "current-session", user?.branchId],
    queryFn: async () => (await attendanceService.current(user!.branchId)).data.session,
    enabled: Boolean(user?.branchId),
    staleTime: 60_000,
  });
  const [state, setState] = useState<KioskState>("idle");
  const [message, setMessage] = useState("");
  const [manual, setManual] = useState(false);
<<<<<<< HEAD
  const contentRef = useRef<HTMLElement>(null);
  const timeout = useRef<number | undefined>(undefined);
  const scanning = state === "camera";
  useFeatureMotion(contentRef, state);
  const reset = useCallback(() => {
=======
  const video = useRef<HTMLVideoElement>(null);
  const contentRef = useRef<HTMLElement>(null);
  const stream = useRef<MediaStream | null>(null);
  const timeout = useRef<number | undefined>(undefined);
  useFeatureMotion(contentRef, state);
  function reset() {
    stream.current?.getTracks().forEach((track) => track.stop());
    stream.current = null;
>>>>>>> origin/main
    setState("idle");
    setManual(false);
    setMessage("");
    window.clearTimeout(timeout.current);
<<<<<<< HEAD
  }, []);
  const scheduleReset = useCallback((delay = 5000) => {
    window.clearTimeout(timeout.current);
    timeout.current = window.setTimeout(reset, delay);
  }, [reset]);
  useEffect(
    () => () => window.clearTimeout(timeout.current),
    [],
  );
  const submit = useCallback(
    async (value: string, kind: "identifier" | "token" = classifyKioskScan(value)) => {
      setState("submitting");
      try {
        const session = currentSession.data;
        if (!session?.id || !user?.branchId) {
          throw new Error("There is no active attendance session for this branch.");
        }
        if (!navigator.onLine) {
          if (kind === "token") {
            throw new Error("QR check-in needs a connection. Use a matric number for offline recovery.");
          }
          const queued = queueAttendanceCheckIn({
            sessionId: session.id,
            branchId: user.branchId,
            memberIdentifier: value,
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
        if (kind === "token") {
          await attendanceService.qrCheckIn({
            token: value,
            sessionId: session.id,
          });
        } else {
          await attendanceService.manual({
            sessionId: session.id,
            branchId: user.branchId,
            identifier: value,
          });
        }
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
    },
    [currentSession.data, scheduleReset, user?.branchId],
  );
  const onScan = useCallback(
    (text: string) => {
      if (state === "camera") void submit(text);
    },
    [state, submit],
  );
  const { videoRef, permissionError } = useQrScanner(onScan, scanning);
  useEffect(() => {
    if (!permissionError) return;
    setState("error");
    setMessage(permissionError);
  }, [permissionError]);
=======
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
      const session = currentSession.data;
      if (!session?.id || !user?.branchId) {
        throw new Error("There is no active attendance session for this branch.");
      }
      if (!navigator.onLine) {
        const queued = queueAttendanceCheckIn({
          sessionId: session.id,
          branchId: user.branchId,
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
      await attendanceService.manual({
        sessionId: session.id,
        branchId: user.branchId,
        identifier,
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
>>>>>>> origin/main
  function manualSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const identifier = String(
      new FormData(event.currentTarget).get("identifier"),
    ).trim();
<<<<<<< HEAD
    if (identifier) void submit(identifier, "identifier");
=======
    if (identifier) void submit(identifier);
>>>>>>> origin/main
  }
  return (
    <main className="kiosk">
      <header>
        <Brand inverse />
        <div>
<<<<<<< HEAD
          <LockKeyhole aria-hidden="true" /> Kiosk mode · administrative navigation disabled
=======
          <LockKeyhole /> Kiosk mode · administrative navigation disabled
>>>>>>> origin/main
        </div>
        <Link to="/app/attendance">Exit kiosk</Link>
      </header>
      <section className="kiosk__content" aria-live="polite" ref={contentRef}>
        {state === "idle" && (
          <>
            <span className="kiosk__icon">
<<<<<<< HEAD
              <QrCode aria-hidden="true" />
=======
              <QrCode />
>>>>>>> origin/main
            </span>
            <p className="eyebrow">Sunday Worship Service</p>
            <h1>Check in to chapel</h1>
            <p>
<<<<<<< HEAD
              Scan a member ChapelFlow identity QR, or enter a matric number.
              This screen clears automatically after every check-in.
            </p>
            <div className="kiosk__buttons">
              <Button onClick={() => { setMessage(""); setState("camera"); }} icon={<Camera />}>
=======
              Use your ChapelFlow QR code or enter your matric number. This
              screen clears automatically after every check-in.
            </p>
            <div className="kiosk__buttons">
              <Button onClick={() => void openCamera()} icon={<Camera />}>
>>>>>>> origin/main
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
            <div className="kiosk__camera" data-scanning="true">
              <video
<<<<<<< HEAD
                ref={videoRef}
=======
                ref={video}
>>>>>>> origin/main
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
<<<<<<< HEAD
            <h1>Hold the ChapelFlow identity QR inside the frame</h1>
            <p>If scanning is unavailable, return and use a matric number.</p>
=======
            <h1>Hold your QR code inside the frame</h1>
            <p>If scanning is unavailable, return and use your identifier.</p>
>>>>>>> origin/main
            <Button variant="secondary" onClick={reset}>
              Cancel scan
            </Button>
          </>
        )}
        {state === "submitting" && (
          <>
            <span className="kiosk__icon kiosk__icon--loading">
<<<<<<< HEAD
              <RotateCcw aria-hidden="true" />
=======
              <RotateCcw />
>>>>>>> origin/main
            </span>
            <h1>Checking you in…</h1>
            <p>Please wait. Do not submit the same code again.</p>
          </>
        )}
        {state === "success" && (
          <>
            <span className="kiosk__icon kiosk__icon--success">
<<<<<<< HEAD
              <CheckCircle2 aria-hidden="true" />
=======
              <CheckCircle2 />
>>>>>>> origin/main
            </span>
            <h1>Check-in confirmed</h1>
            <p>{message}</p>
            <small>
<<<<<<< HEAD
              <Clock3 aria-hidden="true" /> This screen will reset automatically.
=======
              <Clock3 /> This screen will reset automatically.
>>>>>>> origin/main
            </small>
          </>
        )}
        {state === "offline" && (
          <>
            <span className="kiosk__icon kiosk__icon--warning">
<<<<<<< HEAD
              <WifiOff aria-hidden="true" />
=======
              <WifiOff />
>>>>>>> origin/main
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
<<<<<<< HEAD
              <XCircle aria-hidden="true" />
=======
              <XCircle />
>>>>>>> origin/main
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
