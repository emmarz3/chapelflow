import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Camera } from "lucide-react";
import { Link } from "react-router-dom";
import { useState } from "react";
import { EmptyState, ErrorState, LoadingState } from "../components/ui";
import { isDemoMode } from "../lib/fixtures";
import {
  publicService,
  type PublicContentPayload,
} from "../services/chapelflow";
import { GalleryMedia } from "./gallery-media";

const previewAlbums: PublicContentPayload["sections"] = [
  {
    id: "last-semester-worship",
    heading: "Last semester in worship",
    body: "Services and shared moments from the chapel community.",
    imageUrl: "/chapel-hero.jpg",
  },
  {
    id: "community-in-motion",
    heading: "Community in motion",
    body: "Fellowship, service, and life beyond the lecture hall.",
    imageUrl: "/chapelflow-auth-register-visual.png",
  },
];

export function GalleryPage() {
  const [search, setSearch] = useState("");
  const gallery = useQuery({
    queryKey: ["public-content", "gallery"],
    queryFn: async () => (await publicService.content("gallery")).data,
    enabled: !isDemoMode,
    refetchInterval: isDemoMode ? false : 30_000,
  });
  const albums = isDemoMode ? previewAlbums : (gallery.data?.sections ?? []);
  const filtered = albums.filter((item) =>
    `${item.heading} ${item.body}`
      .toLowerCase()
      .includes(search.toLowerCase().trim()),
  );
  return (
    <main className="gallery-page">
      <div className="gallery-container">
        <header className="gallery-heading">
          <p className="eyebrow">Chrisland University Chapel</p>
          <h1>Life together, in frames.</h1>
          <p>
            Photographs, videos, and shared moments from worship, fellowship,
            and service.
          </p>
        </header>
        <div className="gallery-toolbar">
          <div>
            <h2>Recent collections</h2>
            <p>
              {albums.length}{" "}
              {albums.length === 1 ? "collection" : "collections"}
            </p>
          </div>
          <label>
            Find a collection
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search the gallery"
            />
          </label>
        </div>
        {!isDemoMode && gallery.isPending ? (
          <LoadingState label="Opening the chapel gallery" />
        ) : !isDemoMode && gallery.isError ? (
          <ErrorState
            description="The gallery could not be loaded. Please try again."
            onRetry={() => void gallery.refetch()}
          />
        ) : (
          <>
            <div className="gallery-albums">
              {filtered.map((album) => (
                <article className="gallery-card" key={album.id}>
                  <GalleryMedia
                    key={`${album.id}-${album.imageUrl}`}
                    item={album}
                    preview
                  />
                  <div className="gallery-card__body">
                    <span className="gallery-card__type">
                      Collection
                      {album.itemCount !== undefined
                        ? ` · ${album.itemCount} ${album.itemCount === 1 ? "item" : "items"}`
                        : ""}
                    </span>
                    <h2>
                      <Link to={album.action?.href || `/gallery/${album.id}`}>
                        {album.heading || "Chapel moments"}
                      </Link>
                    </h2>
                    {album.body && <p>{album.body}</p>}
                    {album.itemCount !== undefined && (
                      <p className="gallery-card__counts">
                        {album.photoCount || 0} photos · {album.videoCount || 0}{" "}
                        videos
                        {album.fileCount ? ` · ${album.fileCount} files` : ""}
                      </p>
                    )}
                    <Link
                      className="gallery-card__link"
                      to={album.action?.href || `/gallery/${album.id}`}
                    >
                      Open collection <ArrowRight size={16} />
                    </Link>
                  </div>
                </article>
              ))}
            </div>
            {!filtered.length && (
              <EmptyState
                icon={<Camera />}
                title={
                  search
                    ? "No matching collections"
                    : "The gallery is being prepared"
                }
                description={
                  search
                    ? "Try a different collection name."
                    : "Published chapel photographs and videos will appear here."
                }
              />
            )}
          </>
        )}
      </div>
    </main>
  );
}
