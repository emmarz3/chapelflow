import { ProfilePhotoEditor } from "./profile-photo";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent } from "react";

import { ErrorState, LoadingState, PageHeader } from "../components/ui";
import { isStudentMember } from "../lib/permissions";
import { authService } from "../services/chapelflow";
import { useAuth } from "./auth-context";

export function StudentProfileEditorPage() {
  const client = useQueryClient();
  const { user } = useAuth();
  const isStudent = isStudentMember(user);
  const profile = useQuery({
    queryKey: ["student-profile"],
    queryFn: async () => (await authService.studentProfile()).data,
  });
  const update = useMutation({
    mutationFn: (payload: Record<string, string>) =>
      authService.updateStudentProfile(payload),
    onSuccess: () =>
      void client.invalidateQueries({ queryKey: ["student-profile"] }),
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const birthday = String(data.get("date_of_birth") || "");
    update.mutate({
      email: String(data.get("email") || ""),
      phone_number: String(data.get("phone_number") || ""),
      bio: String(data.get("bio") || ""),
      ...(isStudent ? {
        address: String(data.get("address") || ""),
        ...(birthday ? { date_of_birth: birthday } : {}),
        emergency_contact_name: String(data.get("emergency_contact_name") || ""),
        emergency_contact_phone: String(data.get("emergency_contact_phone") || ""),
      } : {}),
    });
  }

  if (profile.isPending) return <LoadingState label="Loading your profile" />;
  if (profile.isError)
    return (
      <ErrorState
        description={profile.error.message}
        onRetry={() => void profile.refetch()}
      />
    );

  const value = profile.data;
  return (
    <>
      <PageHeader
        eyebrow="Personal account"
        title="Edit profile"
        description={
          isStudent
            ? "Update your contact, birthday, photo, and emergency details. Academic fields remain protected."
            : "Update your contact, birthday, photo, and emergency details for ChapelFlow."
        }
      />
      <ProfilePhotoEditor />
      <section className="panel student-profile-editor">
        <form className="student-password-form" onSubmit={submit}>
          <label>
            Email
            <input
              name="email"
              type="email"
              defaultValue={value.email}
              required
            />
          </label>
          <label>
            Phone number
            <input name="phone_number" defaultValue={value.phone_number} />
          </label>
          <label className="field--full">
            Bio
            <textarea
              name="bio"
              defaultValue={value.bio || ""}
              maxLength={200}
              rows={3}
              placeholder="A short introduction about yourself…"
            />
            <small>{(value.bio || "").length}/200 characters. Keep it kind and appropriate for the chapel community.</small>
          </label>
          <label>
            Address
            <input name="address" defaultValue={value.address} />
          </label>
          <label>
            Birthday
            <input
              name="date_of_birth"
              type="date"
              defaultValue={value.date_of_birth || ""}
              max={new Date().toISOString().slice(0, 10)}
            />
          </label>
          <label>
            Emergency contact name
            <input
              name="emergency_contact_name"
              defaultValue={value.emergency_contact_name}
            />
          </label>
          <label>
            Emergency contact phone
            <input
              name="emergency_contact_phone"
              defaultValue={value.emergency_contact_phone}
            />
          </label>
          {update.isError && (
            <p className="form-note form-note--danger">
              {update.error instanceof Error
                ? update.error.message
                : "Profile could not be updated."}
            </p>
          )}
          {update.isSuccess && (
            <p className="form-note form-note--success">Profile updated.</p>
          )}
          <button
            className="button button--primary"
            disabled={update.isPending}
          >
            {update.isPending ? "Saving…" : "Save profile"}
          </button>
        </form>
        <dl className="student-profile-list">
          {isStudent && (
            <>
              <div>
                <dt>Matric number</dt>
                <dd>{value.matric_no || "Not recorded"}</dd>
              </div>
              <div>
                <dt>Department</dt>
                <dd>{value.department || "Not recorded"}</dd>
              </div>
            </>
          )}
          <div>
            <dt>Account type</dt>
            <dd>
              {isStudent
                ? "Student"
                : user?.community === "staff"
                  ? "Staff"
                  : "Guest"}
            </dd>
          </div>
        </dl>
      </section>
    </>
  );
}
