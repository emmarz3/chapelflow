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
    mutationFn: async ({ payload, photo }: { payload: Record<string, string>; photo: File | null }) => {
      if (photo && photo.size) await authService.uploadStudentProfilePhoto(photo);
      return authService.updateStudentProfile(payload);
    },
    onSuccess: () => void client.invalidateQueries({ queryKey: ["student-profile"] }),
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const photo = data.get("profile_photo");
    const birthday = String(data.get("date_of_birth") || "");
    update.mutate({
      payload: {
        email: String(data.get("email") || ""),
        phone_number: String(data.get("phone_number") || ""),
        address: String(data.get("address") || ""),
        ...(birthday ? { date_of_birth: birthday } : {}),
        emergency_contact_name: String(data.get("emergency_contact_name") || ""),
        emergency_contact_phone: String(data.get("emergency_contact_phone") || ""),
      },
      photo: photo instanceof File && photo.name ? photo : null,
    });
  }

  if (profile.isPending) return <LoadingState label="Loading your profile" />;
  if (profile.isError)
    return <ErrorState description={profile.error.message} onRetry={() => void profile.refetch()} />;

  const value = profile.data;
  return (
    <>
      <PageHeader
        eyebrow="Personal account"
        title="Edit profile"
        description={isStudent
          ? "Update your contact, birthday, photo, and emergency details. Academic fields remain protected."
          : "Update your contact, birthday, photo, and emergency details for ChapelFlow."}
      />
      <section className="panel student-profile-editor">
        <form className="student-password-form" onSubmit={submit}>
          <label>Email<input name="email" type="email" defaultValue={value.email} required /></label>
          <label>Phone number<input name="phone_number" defaultValue={value.phone_number} /></label>
          <label>Address<input name="address" defaultValue={value.address} /></label>
          <label>Birthday<input name="date_of_birth" type="date" defaultValue={value.date_of_birth || ""} max={new Date().toISOString().slice(0, 10)} /></label>
          <label>
            Profile photo
            <input name="profile_photo" type="file" accept="image/jpeg,image/png,image/webp,image/gif" />
            <small>Choose a JPG, PNG, WebP, or GIF from your device (up to 10 MB).</small>
            {value.photo_url && <img className="student-profile-editor__photo" src={value.photo_url} alt="Current profile" />}
          </label>
          <label>Emergency contact name<input name="emergency_contact_name" defaultValue={value.emergency_contact_name} /></label>
          <label>Emergency contact phone<input name="emergency_contact_phone" defaultValue={value.emergency_contact_phone} /></label>
          {update.isError && <p className="form-note form-note--danger">{update.error instanceof Error ? update.error.message : "Profile could not be updated."}</p>}
          {update.isSuccess && <p className="form-note form-note--success">Profile updated.</p>}
          <button className="button button--primary" disabled={update.isPending}>{update.isPending ? "Saving…" : "Save profile"}</button>
        </form>
        <dl className="student-profile-list">
          {isStudent && <><div><dt>Matric number</dt><dd>{value.matric_no || "Not recorded"}</dd></div><div><dt>Department</dt><dd>{value.department || "Not recorded"}</dd></div></>}
          <div><dt>Account type</dt><dd>{isStudent ? "Student" : user?.community === "staff" ? "Staff" : "Guest"}</dd></div>
        </dl>
      </section>
    </>
  );
}
