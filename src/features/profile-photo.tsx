import "./profile-photo.css";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { PageHeader } from "../components/ui";
import { authService } from "../services/chapelflow";
import { useAuth } from "./auth-context";

const CROP_SIZE = 320;

function drawCrop(
  image: HTMLImageElement,
  canvas: HTMLCanvasElement,
  zoom: number,
  horizontal: number,
  vertical: number,
) {
  const context = canvas.getContext("2d");
  if (!context) return;
  canvas.width = CROP_SIZE;
  canvas.height = CROP_SIZE;
  const baseScale = Math.max(CROP_SIZE / image.naturalWidth, CROP_SIZE / image.naturalHeight);
  const scale = baseScale * zoom;
  const width = image.naturalWidth * scale;
  const height = image.naturalHeight * scale;
  const offsetX = -(width - CROP_SIZE) * ((horizontal + 100) / 200);
  const offsetY = -(height - CROP_SIZE) * ((vertical + 100) / 200);
  context.clearRect(0, 0, CROP_SIZE, CROP_SIZE);
  context.drawImage(image, offsetX, offsetY, width, height);
}

async function createCroppedPhoto(
  source: File,
  canvas: HTMLCanvasElement,
): Promise<File> {
  const blob = await new Promise<Blob>((resolve, reject) => {
    canvas.toBlob((value) => value ? resolve(value) : reject(new Error("Could not prepare the cropped picture.")), "image/jpeg", 0.9);
  });
  const name = source.name.replace(/\.[^.]+$/, "") || "profile-photo";
  return new File([blob], `${name}-cropped.jpg`, { type: "image/jpeg", lastModified: Date.now() });
}

export function ProfilePhotoEditor() {
  const { user, setProfilePhoto } = useAuth();
  const client = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);
  const objectUrl = useRef("");
  const [file, setFile] = useState<File | null>(null);
  const [imageReady, setImageReady] = useState(false);
  const [validation, setValidation] = useState("");
  const [zoom, setZoom] = useState(1);
  const [horizontal, setHorizontal] = useState(0);
  const [vertical, setVertical] = useState(0);

  useEffect(() => {
    if (!file) {
      setImageReady(false);
      imageRef.current = null;
      if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
      objectUrl.current = "";
      return;
    }
    const url = URL.createObjectURL(file);
    objectUrl.current = url;
    const image = new Image();
    image.onload = () => {
      imageRef.current = image;
      if (canvas.current) drawCrop(image, canvas.current, 1, 0, 0);
      setImageReady(true);
    };
    image.onerror = () => setValidation("This image could not be opened. Choose another picture.");
    image.src = url;
    return () => {
      imageRef.current = null;
      URL.revokeObjectURL(url);
      if (objectUrl.current === url) objectUrl.current = "";
    };
  }, [file]);

  useEffect(() => {
    if (imageRef.current && canvas.current) {
      drawCrop(imageRef.current, canvas.current, zoom, horizontal, vertical);
    }
  }, [zoom, horizontal, vertical]);

  const upload = useMutation({
    mutationFn: (photo: File) => authService.uploadProfilePhoto(photo),
    onSuccess: ({ data }) => {
      setProfilePhoto(data.photo_url);
      setFile(null);
      setZoom(1);
      setHorizontal(0);
      setVertical(0);
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
    setImageReady(false);
    setZoom(1);
    setHorizontal(0);
    setVertical(0);
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

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file || !canvas.current || upload.isPending) return;
    try {
      const cropped = await createCroppedPhoto(file, canvas.current);
      upload.mutate(cropped);
    } catch (error) {
      setValidation(error instanceof Error ? error.message : "Could not crop this picture.");
    }
  }

  return (
    <section className="panel profile-photo-editor" aria-label="Profile picture">
      <header className="panel-heading">
        <div>
          <h2>Profile picture</h2>
          <p>Choose a picture, crop it to a square, and adjust the framing before saving.</p>
        </div>
      </header>
      <div className="profile-photo-editor__preview">
        {file ? (
          <canvas ref={canvas} width={CROP_SIZE} height={CROP_SIZE} aria-label="Cropped profile picture preview" />
        ) : user?.photoUrl ? (
          <img src={user.photoUrl} alt="Current profile picture" />
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
        {file && (
          <div className="profile-photo-editor__crop">
            <label>
              Zoom <output>{zoom.toFixed(1)}×</output>
              <input type="range" min="1" max="3" step="0.05" value={zoom} onChange={(event) => setZoom(Number(event.target.value))} />
            </label>
            <label>
              Horizontal position
              <input type="range" min="-100" max="100" step="1" value={horizontal} onChange={(event) => setHorizontal(Number(event.target.value))} />
            </label>
            <label>
              Vertical position
              <input type="range" min="-100" max="100" step="1" value={vertical} onChange={(event) => setVertical(Number(event.target.value))} />
            </label>
            <button className="button button--secondary" type="button" onClick={() => { setZoom(1); setHorizontal(0); setVertical(0); }}>Reset crop</button>
          </div>
        )}
        <small>JPG, PNG, WebP, or GIF. Maximum 10 MB. The saved picture is a square JPEG crop.</small>
        {(validation || upload.isError) && (
          <p role="alert" className="form-note form-note--danger">
            {validation || upload.error?.message || "Your picture could not be uploaded. Please try again."}
          </p>
        )}
        {upload.isSuccess && <p role="status" className="form-note form-note--success">Profile picture updated.</p>}
        <button className="button button--primary" type="submit" disabled={!file || upload.isPending}>
          {upload.isPending ? "Uploading picture…" : "Save profile picture"}
        </button>
      </form>
    </section>
  );
}

export function AccountProfilePage() {
  return (
    <>
      <PageHeader eyebrow="Your account" title="Profile picture" description="Manage the picture displayed on your ChapelFlow account." />
      <ProfilePhotoEditor />
    </>
  );
}
