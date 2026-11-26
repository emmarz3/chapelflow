import "./profile-photo.css";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { PageHeader } from "../components/ui";
import { authService } from "../services/chapelflow";
import { useAuth } from "./auth-context";

async function cropProfilePhoto(file: File, zoom: number, horizontal: number, vertical: number, dimension: number): Promise<File> {
  const url = URL.createObjectURL(file);
  try {
    const image = new Image();
    image.src = url;
    await image.decode();
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = dimension;
    const context = canvas.getContext("2d");
    if (!context) throw new Error("This browser cannot edit the picture.");
    const side = Math.min(image.naturalWidth, image.naturalHeight) / zoom;
    const left = (image.naturalWidth - side) * (horizontal + 100) / 200;
    const top = (image.naturalHeight - side) * (vertical + 100) / 200;
    context.drawImage(image, left, top, side, side, 0, 0, dimension, dimension);
    const blob = await new Promise<Blob>((resolve, reject) => canvas.toBlob((result) => result ? resolve(result) : reject(new Error("Could not prepare the picture.")), "image/jpeg", 0.88));
    return new File([blob], "profile-picture.jpg", { type: "image/jpeg" });
  } finally {
    URL.revokeObjectURL(url);
  }
}

export function ProfilePhotoEditor() {
  const { user, setProfilePhoto } = useAuth();
  const client = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState("");
  const [validation, setValidation] = useState("");
  const [zoom, setZoom] = useState(1);
  const [horizontal, setHorizontal] = useState(0);
  const [vertical, setVertical] = useState(0);
  const [dimension, setDimension] = useState(512);
  const [edited, setEdited] = useState<File | null>(null);
  const [preparing, setPreparing] = useState(false);
  useEffect(() => {
    if (!file) {
      setPreview("");
      return;
    }
    let active = true;
    setEdited(null);
    setPreparing(true);
    const timer = window.setTimeout(async () => {
      try {
        const output = file.type === "image/gif" ? file : await cropProfilePhoto(file, zoom, horizontal, vertical, dimension);
        if (active) setEdited(output);
      } catch (error) {
        if (active) setValidation(error instanceof Error ? error.message : "Could not edit this picture.");
      } finally {
        if (active) setPreparing(false);
      }
    }, 180);
    return () => { active = false; window.clearTimeout(timer); };
  }, [file, zoom, horizontal, vertical, dimension]);
  useEffect(() => {
    if (!edited) { setPreview(""); return; }
    const url = URL.createObjectURL(edited);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [edited]);
  const upload = useMutation({
    mutationFn: (photo: File) => authService.uploadProfilePhoto(photo),
    onSuccess: ({ data }) => {
      setProfilePhoto(data.photo_url);
      setFile(null);
      setEdited(null);
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
    setEdited(null);
    setZoom(1); setHorizontal(0); setVertical(0); setDimension(512);
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
    if (edited && !preparing && !upload.isPending) upload.mutate(edited);
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
        {file && file.type !== "image/gif" && <div className="profile-photo-editor__controls">
          <label>Zoom <input type="range" min="1" max="3" step="0.05" value={zoom} onChange={(event) => setZoom(Number(event.target.value))} /></label>
          <label>Move left or right <input type="range" min="-100" max="100" value={horizontal} onChange={(event) => setHorizontal(Number(event.target.value))} /></label>
          <label>Move up or down <input type="range" min="-100" max="100" value={vertical} onChange={(event) => setVertical(Number(event.target.value))} /></label>
          <label>Output size <select value={dimension} onChange={(event) => setDimension(Number(event.target.value))}><option value={256}>256 × 256</option><option value={512}>512 × 512</option><option value={1024}>1024 × 1024</option></select></label>
        </div>}
        {file?.type === "image/gif" && <small>Animated GIFs keep their original frames and cannot be cropped here.</small>}
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
          disabled={!edited || preparing || upload.isPending}
        >
          {preparing ? "Preparing preview…" : upload.isPending ? "Uploading picture…" : "Save profile picture"}
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
      <ProfileBioEditor />
    </>
  );
}

export function ProfileBioEditor() {
  const client = useQueryClient();
  const [bio, setBio] = useState<string | null>(null);
  const query = useQuery({ queryKey: ["profile-bio"], queryFn: async () => (await authService.profileBio()).data });
  const save = useMutation({
    mutationFn: authService.updateProfileBio,
    onSuccess: ({ data }) => {
      setBio(data.bio);
      void client.invalidateQueries({ queryKey: ["profile-bio"] });
    },
  });
  return <section className="panel" aria-label="Profile bio">
    <h2>Bio</h2>
    <p>Tell your chapel community a little about yourself. Keep it under 300 characters.</p>
    <form className="student-password-form" onSubmit={(event) => { event.preventDefault(); save.mutate(bio ?? query.data?.bio ?? ""); }}>
      <label>About me
        <textarea value={bio ?? query.data?.bio ?? ""} onChange={(event) => setBio(event.target.value)} maxLength={300} rows={3} disabled={query.isPending || save.isPending} aria-label="About me" />
      </label>
      <small>{(bio ?? query.data?.bio ?? "").length}/300 characters</small>
      {query.isError && <p role="alert">Could not load your bio. <button type="button" onClick={() => void query.refetch()}>Try again</button></p>}
      {save.isError && <p role="alert">{save.error.message}</p>}
      {save.isSuccess && <p role="status">Bio saved.</p>}
      <button className="button button--primary" disabled={query.isPending || save.isPending || query.isError}>Save bio</button>
    </form>
  </section>;
}
