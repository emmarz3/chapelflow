import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent } from "react";
import { ErrorState, LoadingState, PageHeader } from "../components/ui";
import { authService } from "../services/chapelflow";

export function StudentProfileEditorPage() {
  const client = useQueryClient();
  const profile = useQuery({ queryKey: ["student-profile"], queryFn: async () => (await authService.studentProfile()).data });
  const update = useMutation({ mutationFn: authService.updateStudentProfile, onSuccess: () => void client.invalidateQueries({ queryKey: ["student-profile"] }) });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    update.mutate({
      email: String(data.get("email") || ""), phone_number: String(data.get("phone_number") || ""),
      address: String(data.get("address") || ""), photo_url: String(data.get("photo_url") || ""),
      emergency_contact_name: String(data.get("emergency_contact_name") || ""), emergency_contact_phone: String(data.get("emergency_contact_phone") || ""),
    });
  }
  if (profile.isPending) return <LoadingState label="Loading your profile" />;
  if (profile.isError) return <ErrorState description={profile.error.message} onRetry={() => void profile.refetch()} />;
  const value = profile.data;
  return <><PageHeader eyebrow="Personal account" title="Edit profile" description="Update your contact and emergency details. Academic fields remain protected." /><section className="panel student-profile-editor"><form className="student-password-form" onSubmit={submit}><label>Email<input name="email" type="email" defaultValue={value.email} required /></label><label>Phone number<input name="phone_number" defaultValue={value.phone_number} /></label><label>Address<input name="address" defaultValue={value.address} /></label><label>Profile photo URL<input name="photo_url" type="url" defaultValue={value.photo_url} /></label><label>Emergency contact name<input name="emergency_contact_name" defaultValue={value.emergency_contact_name} /></label><label>Emergency contact phone<input name="emergency_contact_phone" defaultValue={value.emergency_contact_phone} /></label>{update.isError && <p className="form-note form-note--danger">{update.error instanceof Error ? update.error.message : "Profile could not be updated."}</p>}{update.isSuccess && <p className="form-note form-note--success">Profile updated.</p>}<button className="button button--primary" disabled={update.isPending}>{update.isPending ? "Saving…" : "Save profile"}</button></form><dl className="student-profile-list"><div><dt>Matric number</dt><dd>{value.matric_no || "Not recorded"}</dd></div><div><dt>Department</dt><dd>{value.department || "Not recorded"}</dd></div><div><dt>Role</dt><dd>Student</dd></div></dl></section></>;
}
