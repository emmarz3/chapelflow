import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { GalleryCollection, GalleryMedia } from "../features/gallery-media";
import type { PublicContentPayload } from "../services/chapelflow";

const content: PublicContentPayload = {
  slug: "worship",
  title: "Worship",
  updatedAt: "",
  sections: [
    {
      id: "photo",
      heading: "Worship photo",
      body: "",
      mediaType: "image",
      imageUrl: "/photo.jpg",
    },
    {
      id: "video",
      heading: "Worship video",
      body: "",
      mediaType: "video",
      imageUrl: "/movie.mp4",
    },
    {
      id: "audio",
      heading: "Choir recording",
      body: "",
      mediaType: "audio",
      mediaUrl: "/choir.mp3",
    },
    {
      id: "pdf",
      heading: "Programme",
      body: "",
      mediaType: "pdf",
      mediaUrl: "/programme.pdf",
      action: {
        label: "Download programme",
        href: "https://example.com/programme.pdf",
      },
    },
  ],
};

describe("Gallery media", () => {
  it("renders real video controls, file links, and type filters", () => {
    render(
      <MemoryRouter>
        <GalleryCollection content={content} />
      </MemoryRouter>,
    );
    const video = screen.getByLabelText("Worship video");
    expect(video.tagName).toBe("VIDEO");
    expect(video).toHaveAttribute("controls");
    expect(video).toHaveAttribute("playsinline");
    expect(
      screen.getByRole("link", { name: "Download programme" }),
    ).toHaveAttribute("href", "https://example.com/programme.pdf");
    fireEvent.click(screen.getByRole("button", { name: "Videos 1" }));
    expect(
      screen.queryByRole("button", { name: "Enlarge Worship photo" }),
    ).not.toBeInTheDocument();
    expect(screen.getByLabelText("Worship video")).toBeInTheDocument();
  });
  it("renders sermon and gallery audio as a native audio player", () => {
    render(<GalleryMedia item={content.sections[2]!} />);
    const audio = screen.getByLabelText("Choir recording");
    expect(audio.tagName).toBe("AUDIO");
    expect(audio).toHaveAttribute("controls");
    expect(audio.querySelector("source")).toHaveAttribute("src", "/choir.mp3");
  });
  it("filters audio resources independently", () => {
    render(
      <MemoryRouter>
        <GalleryCollection content={content} />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Audio 1" }));
    expect(screen.getByLabelText("Choir recording")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Enlarge Worship photo" })).not.toBeInTheDocument();
  });
  it("shows a retry and original link when a preview cannot load", () => {
    render(<GalleryMedia item={content.sections[1]!} />);
    fireEvent.error(screen.getByLabelText("Worship video"));
    expect(
      screen.getByText("Preview could not be loaded."),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open original" })).toHaveAttribute(
      "href",
      "/movie.mp4",
    );
    fireEvent.click(screen.getByRole("button", { name: "Retry preview" }));
    expect(screen.getByLabelText("Worship video")).toBeInTheDocument();
  });
  it("opens full photos in a dismissible dialog", () => {
    const show = vi.fn();
    HTMLDialogElement.prototype.showModal = show;
    render(<GalleryMedia item={content.sections[0]!} />);
    fireEvent.click(
      screen.getByRole("button", { name: "Enlarge Worship photo" }),
    );
    expect(show).toHaveBeenCalled();
  });
  it("uses an honest placeholder for albums with no preview", () => {
    render(<GalleryMedia item={{ id: "empty", body: "" }} preview />);
    expect(screen.getByText("No preview available")).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });
});
