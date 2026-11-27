import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, FileText, Image as ImageIcon, X } from "lucide-react";
import type { PublicContentPayload } from "../services/chapelflow";
import "./gallery.css";

type Item = PublicContentPayload["sections"][number];
export function GalleryMedia({
  item,
  preview = false,
}: {
  item: Item;
  preview?: boolean;
}) {
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const dialog = useRef<HTMLDialogElement>(null);
  const source = item.mediaUrl || item.imageUrl;
  const label = item.imageAlt || item.heading || "Chapel photograph";
  if (failed)
    return (
      <div className="gallery-media gallery-media--empty">
        <ImageIcon aria-hidden="true" />
        <p>Preview could not be loaded.</p>
        {item.mediaType === "video" && (
          <p>
            This browser may not support the uploaded video format. You can open
            the original file below.
          </p>
        )}
        <button
          type="button"
          onClick={() => {
            setFailed(false);
            setAttempt((value) => value + 1);
          }}
        >
          Retry preview
        </button>
        {source && (
          <a href={source} target="_blank" rel="noreferrer">
            Open original
          </a>
        )}
      </div>
    );
  if (!source || item.mediaType === "file" || item.mediaType === "pdf")
    return (
      <div className="gallery-media gallery-media--empty">
        {item.mediaType === "file" || item.mediaType === "pdf" ? (
          <FileText aria-hidden="true" />
        ) : (
          <ImageIcon aria-hidden="true" />
        )}
        <span>
          {item.mediaType === "pdf"
            ? "PDF document"
            : item.mediaType === "file"
              ? "Downloadable resource"
              : "No preview available"}
        </span>
      </div>
    );
  if (item.mediaType === "audio" && source)
    return (
      <div className="gallery-media gallery-media--audio">
        <audio controls preload="metadata" aria-label={item.heading || "Chapel audio"}>
          <source src={source} />
        </audio>
      </div>
    );
  if (item.mediaType === "video")
    return (
      <div className="gallery-media">
        <video
          key={`${source}-${attempt}`}
          controls
          playsInline
          preload="metadata"
          aria-label={item.heading || "Chapel video"}
          src={source}
          onError={() => setFailed(true)}
        />
      </div>
    );
  return (
    <>
      <div className="gallery-media">
        {preview ? (
          <img
            src={source}
            alt={label}
            loading="lazy"
            onError={() => setFailed(true)}
          />
        ) : (
          <button
            className="gallery-media__expand"
            type="button"
            aria-label={`Enlarge ${label}`}
            onClick={() => dialog.current?.showModal()}
          >
            <img
              src={source}
              alt={label}
              loading="lazy"
              onError={() => setFailed(true)}
            />
            <span>View full photo</span>
          </button>
        )}
      </div>
      {!preview && (
        <dialog
          className="gallery-lightbox"
          ref={dialog}
          aria-label={label}
          onClick={(event) => {
            if (event.target === event.currentTarget) dialog.current?.close();
          }}
        >
          <button
            className="gallery-lightbox__close"
            type="button"
            autoFocus
            onClick={() => dialog.current?.close()}
            aria-label="Close photo"
          >
            <X />
          </button>
          <img src={source} alt={label} />
          <p>{item.heading}</p>
        </dialog>
      )}
    </>
  );
}

export function GalleryCollection({
  content,
}: {
  content: PublicContentPayload;
}) {
  const [filter, setFilter] = useState("all");
  const types = [
    { value: "all", label: "All media" },
    { value: "image", label: "Photos" },
    { value: "video", label: "Videos" },
    { value: "audio", label: "Audio" },
    { value: "pdf", label: "PDFs" },
    { value: "file", label: "Files" },
  ];
  const items = content.sections.filter(
    (item) => filter === "all" || (item.mediaType || "image") === filter,
  );
  return (
    <main className="gallery-page">
      <div className="gallery-container">
        <Link className="gallery-back" to="/gallery">
          <ArrowLeft size={18} /> All collections
        </Link>
        <header className="gallery-heading">
          <p className="eyebrow">Chapel gallery</p>
          <h1>{content.title}</h1>
          {content.description && <p>{content.description}</p>}
          <span>
            {content.sections.length}{" "}
            {content.sections.length === 1 ? "item" : "items"}
          </span>
        </header>
        <div className="gallery-filters" aria-label="Filter gallery media">
          {types.map(({ value, label }) => (
            <button
              key={value}
              type="button"
              aria-pressed={filter === value}
              onClick={() => setFilter(value)}
            >
              {label}{" "}
              <span>
                {
                  content.sections.filter(
                    (item) =>
                      value === "all" || (item.mediaType || "image") === value,
                  ).length
                }
              </span>
            </button>
          ))}
        </div>
        <div className="gallery-items">
          {items.map((item) => (
            <article className="gallery-card" key={item.id}>
              <GalleryMedia key={`${item.id}-${item.imageUrl}`} item={item} />
              <div className="gallery-card__body">
                <span className="gallery-card__type">
                  {item.mediaType === "video"
                    ? "Video"
                    : item.mediaType === "audio"
                      ? "Audio"
                      : item.mediaType === "pdf"
                        ? "PDF"
                        : item.mediaType === "file"
                          ? "File"
                          : "Photo"}
                </span>
                {item.heading && <h2>{item.heading}</h2>}
                {item.body && <p>{item.body}</p>}
                {item.action && (
                  <a
                    className="gallery-card__link"
                    href={item.action.href}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {item.action.label}
                  </a>
                )}
              </div>
            </article>
          ))}
        </div>
        {!items.length && (
          <p className="gallery-empty" role="status">
            {content.sections.length
              ? "No media of this type in this collection."
              : "This collection has no published media yet."}
          </p>
        )}
      </div>
    </main>
  );
}
