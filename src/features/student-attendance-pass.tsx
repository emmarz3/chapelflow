import { useQuery } from "@tanstack/react-query";
import { Clock3, QrCode, RefreshCw, ShieldCheck } from "lucide-react";
import { useRef } from "react";
import {
  Badge,
  Button,
  ErrorState,
  LoadingState,
  PageHeader,
} from "../components/ui";
import { useFeatureMotion } from "../components/motion/motion-system";
import { attendanceService } from "../services/chapelflow";

export function StudentAttendancePassPage() {
  const pageRef = useRef<HTMLDivElement>(null);
  const pass = useQuery({
    queryKey: ["attendance-pass"],
    queryFn: async () => (await attendanceService.pass()).data,
    refetchInterval: 60_000,
    refetchOnWindowFocus: true,
  });
  const history = useQuery({
    queryKey: ["attendance-history", "me"],
    queryFn: async () => (await attendanceService.history()).data,
  });
  useFeatureMotion(pageRef, pass.data?.expiresAt ?? pass.status);

  if (pass.isPending)
    return <LoadingState label="Preparing your secure chapel pass" />;
  if (pass.isError) {
    return (
      <ErrorState
        description={pass.error.message}
        onRetry={() => void pass.refetch()}
      />
    );
  }

  const data = pass.data;
  return (
    <div className="motion-feature motion-feature--pass" ref={pageRef}>
      <PageHeader
        eyebrow="Student attendance"
        title="My Chapel Pass"
        description="Your secure pass refreshes automatically while an attendance session is active."
        actions={
          <Button
            variant="secondary"
            icon={<RefreshCw />}
            onClick={() => void pass.refetch()}
          >
            Refresh pass
          </Button>
        }
      />
      <section className="chapel-pass" aria-live="polite">
        <header>
          <div className="chapel-pass__mark">
            <QrCode />
          </div>
          <div>
            <small>Chrisland University Chapel</small>
            <h2>ChapelFlow Attendance Pass</h2>
          </div>
          <Badge tone={data.passStatus === "active" ? "success" : "danger"}>
            {data.passStatus}
          </Badge>
        </header>
        <div className="chapel-pass__body">
          <div className="chapel-pass__identity">
            <span className="profile-summary__avatar">
              {data.student.name
                .split(/\s+/)
                .slice(0, 2)
                .map((part) => part[0])
                .join("")}
            </span>
            <h3>{data.student.name}</h3>
            <strong>{data.student.identifier}</strong>
            <p>{data.student.programme || "Programme not provided"}</p>
            {data.student.level && <small>Level {data.student.level}</small>}
          </div>
          <div className="chapel-pass__qr">
            {data.imageDataUrl ? (
              <img
                src={data.imageDataUrl}
                alt="Your rotating ChapelFlow attendance QR code"
              />
            ) : (
              <div className="chapel-pass__unavailable">
                <Clock3 />
                <strong>No active chapel session</strong>
                <p>
                  Your QR pass will appear when an administrator opens
                  attendance.
                </p>
              </div>
            )}
            {data.session && <strong>{data.session.title}</strong>}
            {data.expiresAt && (
              <small>
                Refreshes by {new Date(data.expiresAt).toLocaleTimeString()}
              </small>
            )}
          </div>
        </div>
        <footer>
          <ShieldCheck />
          <span>
            Present this QR code to an authorized chapel usher for attendance.
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
