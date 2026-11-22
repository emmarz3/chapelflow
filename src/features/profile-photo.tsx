import "./profile-photo.css";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { PageHeader } from "../components/ui";
import { authService } from "../services/chapelflow";
import { useAuth } from "./auth-context";

export function ProfilePhotoEditor() {
  const { user, setProfilePhoto } = useAuth();
  const client = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState("");
  const [validation, setValidation] = useState("");
  useEffect(() => {
    if (!file) {
      setPreview("");
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
  const upload = useMutation({
    mutationFn: (photo: File) => authService.uploadProfilePhoto(photo),
    onSuccess: ({ data }) => {
      setProfilePhoto(data.photo_url);
      setFile(null);
      if (input.current) input.current.value = "";
      for (const key of ["student-profile", "attendance-pass", "members"]) {
        void client.invalidateQueries({ queryKey: [key] });
      }
    },
  });
  function select(photo: File | null) {
    upload.reset();
    setValidation("");
    setFile(null);
    if (!photo) return;
    if (
      !/^image\/(jpeg|png|webp|gif)$/.test(photo.type) ||
      photo.size > 10 * 1024 * 1024 ||
      !photo.size
    ) {
      setValidation("Choose a JPG, PNG, WebP, or GIF image up to 10 MB.");
      if (input.current) input.current.value = "";
      return;
    }
    setFile(photo);
  }
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (file && !upload.isPending) upload.mutate(file);
  }
  return (
    <section
      className="panel profile-photo-editor"
      aria-label="Profile picture"
    >
      <header className="panel-heading">
        <div>
          <h2>Profile picture</h2>
          <p>Add a picture so people can recognise you on ChapelFlow.</p>
        </div>
      </header>
      <div className="profile-photo-editor__preview">
        {preview || user?.photoUrl ? (
          <img
            src={preview || user?.photoUrl}
            alt={
              preview
                ? "Selected profile picture preview"
                : "Current profile picture"
            }
          />
        ) : (
          <span aria-label="No profile picture">{user?.initials}</span>
        )}
      </div>
      <form className="student-password-form" onSubmit={submit}>
        <label>
          Choose profile picture
          <input
            ref={input}
            type="file"
            accept="image/jpeg,image/png,image/webp,image/gif"
            disabled={upload.isPending}
            onChange={(event) => select(event.target.files?.[0] ?? null)}
          />
        </label>
        <small>
          JPG, PNG, WebP, or GIF. Maximum 10 MB. Uploading replaces your current
          picture.
        </small>
        {(validation || upload.isError) && (
          <p role="alert" className="form-note form-note--danger">
            {validation ||
              upload.error?.message ||
              "Your picture could not be uploaded. Please try again."}
          </p>
        )}
        {upload.isSuccess && (
          <p role="status" className="form-note form-note--success">
            Profile picture updated.
          </p>
        )}
        <button
          className="button button--primary"
          type="submit"
          disabled={!file || upload.isPending}
        >
          {upload.isPending ? "Uploading picture…" : "Save profile picture"}
        </button>
      </form>
    </section>
  );
}

export function AccountProfilePage() {
  return (
    <>
      <PageHeader
        eyebrow="Your account"
        title="Profile picture"
        description="Manage the picture displayed on your ChapelFlow account."
      />
      <ProfilePhotoEditor />
    </>
  );
}
