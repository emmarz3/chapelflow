import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bell, Clock3, Compass, Copy, Heart, Home, ImagePlus, MessageCircle,
  PlusSquare, Search, Send, Share2, Sparkles, Trash2, Video, X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Button, EmptyState, ErrorState, LoadingState, useToast } from "../components/ui";
import {
  upperRoomService,
  type UpperRoomMedia,
  type UpperRoomPost,
  type UpperRoomStory,
} from "../services/chapelflow";
import { useAuth } from "./auth-context";
import { ReportContentButton } from "./moderation";

const MAX_MEDIA_BYTES = 50 * 1024 * 1024;

function failureMessage(error: unknown) {
  return error instanceof Error ? error.message : "The Upper Room could not complete that action. Try again.";
}

function relativeTime(value: string) {
  const seconds = Math.max(0, Math.round((Date.now() - new Date(value).getTime()) / 1000));
  if (seconds < 60) return "now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86_400) return `${Math.floor(seconds / 3600)}h`;
  return new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short" }).format(new Date(value));
}

function initials(name: string) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase() || "CF";
}

const UPPER_ROOM_MEDIA_TYPES: Record<string, string> = {
  jpg: "image/jpeg", jpeg: "image/jpeg", png: "image/png", gif: "image/gif",
  webp: "image/webp", mp4: "video/mp4", mov: "video/quicktime", webm: "video/webm",
};

function mediaFileError(file: File) {
  const extension = file.name.includes(".") ? file.name.split(".").pop()!.toLowerCase() : "";
  if (!UPPER_ROOM_MEDIA_TYPES[extension] || file.type !== UPPER_ROOM_MEDIA_TYPES[extension]) {
    return `${file.name}: use JPG, PNG, GIF, WebP, MP4, MOV, or WebM media.`;
  }
  if (!file.size || file.size > MAX_MEDIA_BYTES) {
    return `${file.name}: each photo or video must be 50 MB or smaller.`;
  }
  return null;
}

interface RecentMedia {
  id: string;
  postId: string;
  url: string;
  mediaType: "IMAGE" | "VIDEO";
  caption: string;
  authorName: string;
  viewedAt: string;
}

function loadRecent(key: string | null): RecentMedia[] {
  if (!key) return [];
  try {
    const value = localStorage.getItem(key);
    const parsed = value ? JSON.parse(value) as RecentMedia[] : [];
    return Array.isArray(parsed) ? parsed.slice(0, 12) : [];
  } catch {
    return [];
  }
}

export function UpperRoomPage() {
  const { user } = useAuth();
  const toast = useToast();
  const client = useQueryClient();
  const storyInput = useRef<HTMLInputElement>(null);
  const [caption, setCaption] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [selectedBranch, setSelectedBranch] = useState("");
  const [storyFile, setStoryFile] = useState<File | null>(null);
  const [storyCaption, setStoryCaption] = useState("");
  const [storyPreview, setStoryPreview] = useState("");
  const [storyComposerOpen, setStoryComposerOpen] = useState(false);
  const [viewingStoryId, setViewingStoryId] = useState<string | null>(null);
  const [viewingMedia, setViewingMedia] = useState<RecentMedia | null>(null);
  const recentKey = user?.id ? `chapelflow-upper-room-recent-${user.id}` : null;
  const [recent, setRecent] = useState<RecentMedia[]>(() => loadRecent(recentKey));

  useEffect(() => {
    setRecent(loadRecent(recentKey));
  }, [recentKey]);

  useEffect(() => {
    if (!recentKey) return;
    try {
      localStorage.setItem(recentKey, JSON.stringify(recent.slice(0, 12)));
    } catch {
      // Private browsing or a full storage quota should not block the feed.
    }
  }, [recent, recentKey]);

  useEffect(() => {
    if (!storyFile) {
      setStoryPreview("");
      return;
    }
    const url = URL.createObjectURL(storyFile);
    setStoryPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [storyFile]);

  const feed = useQuery({
    queryKey: ["upper-room", 1],
    queryFn: async () => (await upperRoomService.feed()).data,
    staleTime: 30_000,
    gcTime: 10 * 60_000,
    retry: 1,
    refetchOnWindowFocus: false,
  });
  const stories = useQuery({
    queryKey: ["upper-room-stories", selectedBranch || user?.branchId || "mine"],
    queryFn: async () => (await upperRoomService.stories(selectedBranch || undefined)).data,
    enabled: Boolean(user) && (user?.role !== "super_admin" || Boolean(selectedBranch)),
    staleTime: 30_000,
    gcTime: 10 * 60_000,
    retry: 1,
  });

  const publish = useMutation({
    mutationFn: () => upperRoomService.createPost(caption.trim(), files, selectedBranch || undefined),
    onSuccess: () => {
      setCaption("");
      setFiles([]);
      toast("Shared in The Upper Room.");
      void client.invalidateQueries({ queryKey: ["upper-room"] });
    },
    onError: (error) => toast(failureMessage(error), "error"),
  });

  const publishStory = useMutation({
    mutationFn: () => storyFile
      ? upperRoomService.createStory(storyFile, storyCaption.trim(), selectedBranch || undefined)
      : Promise.reject(new Error("Choose a photo or video for your story.")),
    onSuccess: () => {
      setStoryFile(null);
      setStoryCaption("");
      setStoryComposerOpen(false);
      if (storyInput.current) storyInput.current.value = "";
      toast("Your story is live for 24 hours.");
      void client.invalidateQueries({ queryKey: ["upper-room-stories"] });
    },
    onError: (error) => toast(failureMessage(error), "error"),
  });

  function recordRecent(item: Omit<RecentMedia, "viewedAt">) {
    const entry: RecentMedia = { ...item, viewedAt: new Date().toISOString() };
    setRecent((current) => [entry, ...current.filter((row) => row.id !== entry.id)].slice(0, 12));
  }

  function openPostMedia(post: UpperRoomPost, media: UpperRoomMedia) {
    const item: RecentMedia = {
      id: media.id,
      postId: post.id,
      url: media.url,
      mediaType: media.mediaType,
      caption: post.caption,
      authorName: post.authorName,
      viewedAt: new Date().toISOString(),
    };
    recordRecent(item);
    setViewingMedia(item);
  }

  function handleFiles(selected: File[]) {
    if (selected.length > 4) {
      toast("Add up to four photos or videos in one post.", "error");
      return;
    }
    const invalid = selected.map(mediaFileError).find(Boolean);
    if (invalid) {
      toast(invalid, "error");
      return;
    }
    setFiles(selected);
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (user?.role === "super_admin" && !selectedBranch) {
      toast("Select a chapel branch before sharing.", "error");
      return;
    }
    if (!caption.trim() && !files.length) {
      toast("Add a caption, photo, or video before sharing.", "error");
      return;
    }
    if (!publish.isPending) publish.mutate();
  }

  function selectStoryFile(file: File | null) {
    if (!file) return;
    const invalid = mediaFileError(file);
    if (invalid) {
      toast(invalid, "error");
      if (storyInput.current) storyInput.current.value = "";
      return;
    }
    setStoryFile(file);
    setStoryComposerOpen(true);
  }

  const posts = feed.data?.items ?? [];
  const activeStory = stories.data?.find((story) => story.id === viewingStoryId) ?? null;

  if (feed.isPending) return <LoadingState label="Opening The Upper Room" />;
  if (feed.isError) return <ErrorState description={failureMessage(feed.error)} onRetry={() => void feed.refetch()} />;

  return (
    <div className="upper-room">
      <header className="upper-room__topbar">
        <div className="upper-room__brand"><span className="upper-room__brand-mark" aria-hidden="true"><Sparkles /></span><strong>The Upper Room</strong></div>
        <label className="upper-room__search"><Search /><input aria-label="Search The Upper Room" placeholder="Search" /></label>
        <nav aria-label="Upper Room actions">
          <button type="button" aria-label="Home"><Home /></button>
          <button type="button" aria-label="Create a post" onClick={() => document.getElementById("upper-room-caption")?.focus()}><PlusSquare /></button>
          <button type="button" aria-label="Explore"><Compass /></button>
          <button type="button" aria-label="Notifications"><Bell /></button>
          <button type="button" aria-label="Messages"><MessageCircle /></button>
        </nav>
      </header>

      <div className="upper-room__layout">
        <main className="upper-room__main">
          <section className="upper-room__stories" aria-label="Upper Room stories">
            <button type="button" className="upper-room__story upper-room__story--create" onClick={() => storyInput.current?.click()}>
              <span className="upper-room__story-ring"><span><PlusSquare /></span></span>
              <small>Your story</small>
            </button>
            {(stories.data ?? []).map((story) => (
              <button type="button" key={story.id} className="upper-room__story" onClick={() => setViewingStoryId(story.id)}>
                <span className="upper-room__story-ring upper-room__story-ring--1">
                  {story.mediaType === "IMAGE" ? <img src={story.mediaUrl} alt="" loading="lazy" /> : <span><Video /></span>}
                </span>
                <small>{story.authorName.split(" ")[0]}</small>
              </button>
            ))}
            <input
              ref={storyInput}
              className="sr-only"
              type="file"
              accept="image/jpeg,image/png,image/gif,image/webp,video/mp4,video/quicktime,video/webm"
              onChange={(event) => selectStoryFile(event.currentTarget.files?.[0] ?? null)}
            />
            {stories.isError && <small role="status">Stories are temporarily unavailable. <button type="button" onClick={() => void stories.refetch()}>Retry</button></small>}
          </section>

          {user?.role === "super_admin" && (
            <label className="upper-room__branch-picker">Post to chapel branch
              <select value={selectedBranch} onChange={(event) => setSelectedBranch(event.target.value)} required>
                <option value="">Select a branch</option>
                {(feed.data?.branches ?? []).map((branch) => <option key={branch.id} value={branch.id}>{branch.name}</option>)}
              </select>
            </label>
          )}

          {storyComposerOpen && storyFile && (
            <section className="upper-room__story-composer panel" aria-label="Create your story">
              <header>
                <div><strong>New story</strong><small>Visible to your chapel branch for 24 hours</small></div>
                <button type="button" aria-label="Close story composer" onClick={() => { setStoryComposerOpen(false); setStoryFile(null); setStoryCaption(""); }}><X /></button>
              </header>
              <div className="upper-room__story-preview">
                {storyFile.type.startsWith("video/") ? <video src={storyPreview} controls playsInline /> : <img src={storyPreview} alt="Story preview" />}
              </div>
              <label className="field">
                Caption (optional)
                <textarea value={storyCaption} onChange={(event) => setStoryCaption(event.target.value)} maxLength={280} rows={2} placeholder="Add a short note…" />
              </label>
              <small>{(storyCaption || "").length}/280 · Maximum file size 50 MB</small>
              <Button type="button" loading={publishStory.isPending} disabled={!storyFile || (user?.role === "super_admin" && !selectedBranch)} onClick={() => publishStory.mutate()}>
                Share story <Send size={16} />
              </Button>
              {publishStory.isError && <p className="form-error" role="alert">{failureMessage(publishStory.error)}</p>}
            </section>
          )}

          <section className="upper-room__composer panel" aria-label="Create an Upper Room post">
            <div className="upper-room__avatar" aria-hidden="true">{user?.photoUrl ? <img src={user.photoUrl} alt="" /> : initials(user?.name || "")}</div>
            <form onSubmit={submit}>
              <label className="sr-only" htmlFor="upper-room-caption">Share with The Upper Room</label>
              <textarea id="upper-room-caption" value={caption} onChange={(event) => setCaption(event.target.value)} maxLength={1000} rows={3} placeholder="Share a thought, a praise report, or a moment from chapel…" />
              {files.length > 0 && (
                <div className="upper-room__files">
                  {files.map((file, index) => (
                    <span key={`${file.name}-${index}`}>
                      {file.type.startsWith("video/") ? <Video aria-hidden="true" /> : <ImagePlus aria-hidden="true" />}
                      {file.name}
                      <button type="button" aria-label={`Remove ${file.name}`} onClick={() => setFiles((items) => items.filter((_, itemIndex) => itemIndex !== index))}><X /></button>
                    </span>
                  ))}
                </div>
              )}
              <div className="upper-room__composer-actions">
                <label className="upper-room__file-picker"><ImagePlus /> Add photos or videos
                  <input
                    type="file"
                    accept=".jpg,.jpeg,.png,.gif,.webp,.mp4,.mov,.webm,image/jpeg,image/png,image/gif,image/webp,video/mp4,video/quicktime,video/webm"
                    multiple
                    onChange={(event) => {
                      const selected = Array.from(event.currentTarget.files ?? []);
                      event.currentTarget.value = "";
                      handleFiles(selected);
                    }}
                  />
                </label>
                <small>JPG, PNG, GIF, WebP, MP4, MOV or WebM · 50 MB per file · up to 4 files</small>
                <Button type="submit" loading={publish.isPending} disabled={publish.isPending} icon={<Send />}>Share</Button>
              </div>
              {publish.isError && <p className="form-error" role="alert">{failureMessage(publish.error)}</p>}
            </form>
          </section>

          {recent.length > 0 && (
            <section className="upper-room__recent" aria-label="Recently viewed media">
              <header><div><Clock3 /><strong>Recently viewed</strong></div><button type="button" onClick={() => setRecent([])}>Clear history</button></header>
              <div className="upper-room__recent-list">
                {recent.map((item) => (
                  <button type="button" key={item.id} onClick={() => setViewingMedia(item)}>
                    <span>{item.mediaType === "IMAGE" ? <img src={item.url} alt="" loading="lazy" /> : <span className="upper-room__recent-video"><Video /></span>}</span>
                    <small>{item.authorName} · {relativeTime(item.viewedAt)}</small>
                  </button>
                ))}
              </div>
            </section>
          )}

          <section className="upper-room__feed" aria-label="Upper Room posts">
            {posts.length ? posts.map((post) => (
              <PostCard key={post.id} post={post} onOpenMedia={openPostMedia} />
            )) : (
              <EmptyState icon={<MessageCircle />} title="The room is ready" description="Be the first person in your chapel community to share a photo, video, or encouraging word." />
            )}
          </section>
        </main>
        <aside className="upper-room__sidebar">
          <div className="upper-room__profile">
            <div className="upper-room__avatar">{user?.photoUrl ? <img src={user.photoUrl} alt="" /> : initials(user?.name || "")}</div>
            <div><strong>{user?.name || "Chapel member"}</strong><small>Chrisland University Chapel</small></div>
          </div>
          <div className="upper-room__suggestions"><header><strong>Suggested for you</strong></header><p>Follow the moments and people making chapel life meaningful.</p><span><Sparkles /> Share with care. Keep the grace.</span></div>
        </aside>
      </div>

      <nav className="upper-room__mobile-nav" aria-label="Upper Room mobile navigation">
        <button type="button" aria-label="Home"><Home /></button>
        <button type="button" aria-label="Search"><Search /></button>
        <button type="button" aria-label="Create a post" onClick={() => document.getElementById("upper-room-caption")?.focus()}><PlusSquare /></button>
        <button type="button" aria-label="Notifications"><Heart /></button>
        <span className="upper-room__avatar" aria-hidden="true">{user?.photoUrl ? <img src={user.photoUrl} alt="" /> : initials(user?.name || "")}</span>
      </nav>

      {activeStory && (
        <div className="upper-room__viewer" role="dialog" aria-modal="true" aria-label="Upper Room story" onClick={() => setViewingStoryId(null)}>
          <div className="upper-room__viewer-card" onClick={(event) => event.stopPropagation()}>
            <header><div><strong>{activeStory.authorName}</strong><small>{relativeTime(activeStory.createdAt)} · expires in 24 hours</small></div><button type="button" aria-label="Close story" onClick={() => setViewingStoryId(null)}><X /></button></header>
            {activeStory.mediaType === "VIDEO" ? <video src={activeStory.mediaUrl} controls autoPlay playsInline /> : <img src={activeStory.mediaUrl} alt={activeStory.caption || "Upper Room story"} />}
            {activeStory.caption && <p>{activeStory.caption}</p>}
          </div>
        </div>
      )}

      {viewingMedia && (
        <div className="upper-room__viewer" role="dialog" aria-modal="true" aria-label="Recently viewed media" onClick={() => setViewingMedia(null)}>
          <div className="upper-room__viewer-card" onClick={(event) => event.stopPropagation()}>
            <header><div><strong>{viewingMedia.authorName}</strong><small>{viewingMedia.caption || "The Upper Room"}</small></div><button type="button" aria-label="Close media" onClick={() => setViewingMedia(null)}><X /></button></header>
            {viewingMedia.mediaType === "VIDEO" ? <video src={viewingMedia.url} controls autoPlay playsInline /> : <img src={viewingMedia.url} alt={viewingMedia.caption || "Upper Room media"} />}
          </div>
        </div>
      )}
    </div>
  );
}

function PostCard({ post, onOpenMedia }: { post: UpperRoomPost; onOpenMedia: (post: UpperRoomPost, media: UpperRoomMedia) => void }) {
  const { user } = useAuth();
  const toast = useToast();
  const client = useQueryClient();
  const [showComments, setShowComments] = useState(false);
  const [comment, setComment] = useState("");
  const [shareOpen, setShareOpen] = useState(false);
  const comments = useQuery({
    queryKey: ["upper-room-comments", post.id],
    queryFn: async () => (await upperRoomService.comments(post.id)).data,
    enabled: showComments,
    staleTime: 30_000,
  });
  const like = useMutation({
    mutationFn: () => upperRoomService.toggleLike(post.id),
    onSuccess: () => void client.invalidateQueries({ queryKey: ["upper-room"] }),
    onError: (error) => toast(failureMessage(error), "error"),
  });
  const remove = useMutation({
    mutationFn: () => upperRoomService.deletePost(post.id),
    onSuccess: () => { toast("Post removed."); void client.invalidateQueries({ queryKey: ["upper-room"] }); },
    onError: (error) => toast(failureMessage(error), "error"),
  });
  const addComment = useMutation({
    mutationFn: () => upperRoomService.createComment(post.id, comment.trim()),
    onSuccess: () => { setComment(""); void client.invalidateQueries({ queryKey: ["upper-room-comments", post.id] }); void client.invalidateQueries({ queryKey: ["upper-room"] }); },
    onError: (error) => toast(failureMessage(error), "error"),
  });
  const isOwnPost = post.authorName === user?.name;
  const canModerate = ["super_admin", "chapel_admin", "chaplain", "student_chaplain"].includes(user?.role ?? "");
  const shareUrl = `${window.location.origin}/app/upper-room?post=${encodeURIComponent(post.id)}`;

  async function share() {
    try {
      if (navigator.share) {
        await navigator.share({
          title: "The Upper Room · ChapelFlow",
          text: post.caption || `A post shared by ${post.authorName} in The Upper Room.`,
          url: shareUrl,
        });
        setShareOpen(false);
      } else {
        await navigator.clipboard.writeText(shareUrl);
        toast("Post link copied.");
        setShareOpen(false);
      }
    } catch (error) {
      if (error instanceof Error && error.name !== "AbortError") {
        try {
          await navigator.clipboard.writeText(shareUrl);
          toast("Post link copied.");
          setShareOpen(false);
        } catch {
          toast("This browser could not share or copy the link.", "error");
        }
      }
    }
  }

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(shareUrl);
      toast("Post link copied.");
      setShareOpen(false);
    } catch {
      toast("Could not copy the link on this device.", "error");
    }
  }

  return (
    <>
      <article className="upper-room-post panel">
        <header>
          <div className="upper-room__avatar" aria-hidden="true">{initials(post.authorName)}</div>
          <div><strong>{post.authorName}</strong><small>{relativeTime(post.createdAt)} · {post.branchName || "The Upper Room"}</small></div>
          {(isOwnPost || canModerate) && <button className="icon-button" type="button" aria-label="Remove post" disabled={remove.isPending} onClick={() => { if (window.confirm("Remove this post from The Upper Room?")) remove.mutate(); }}><Trash2 /></button>}
        </header>
        {post.caption && <p className="upper-room-post__caption">{post.caption}</p>}
        {post.media.length > 0 && (
          <div className={`upper-room-post__media upper-room-post__media--${Math.min(post.media.length, 4)}`}>
            {post.media.map((media) => media.mediaType === "VIDEO" ? (
              <video key={media.id} controls preload="metadata" playsInline onPlay={() => onOpenMedia(post, media)}>
                <source src={media.url} />
              </video>
            ) : (
              <button key={media.id} type="button" className="upper-room-post__image-button" onClick={() => onOpenMedia(post, media)} aria-label="Open shared photo">
                <img src={media.url} alt="Shared Upper Room post" loading="lazy" />
              </button>
            ))}
          </div>
        )}
        <div className="upper-room-post__counts">
          <span>{post.likeCount ? `${post.likeCount} ${post.likeCount === 1 ? "like" : "likes"}` : "Be the first to like this"}</span>
          <button type="button" onClick={() => setShowComments((open) => !open)}>{post.commentCount ? `${post.commentCount} ${post.commentCount === 1 ? "comment" : "comments"}` : "Comment"}</button>
        </div>
        <div className="upper-room-post__actions">
          <button type="button" className={post.isLiked ? "is-liked" : ""} disabled={like.isPending} onClick={() => like.mutate()}><Heart fill={post.isLiked ? "currentColor" : "none"} /> {post.isLiked ? "Liked" : "Like"}</button>
          <button type="button" onClick={() => setShowComments((open) => !open)}><MessageCircle /> Comment</button>
          <button type="button" onClick={() => setShareOpen(true)}><Share2 /> Share</button>
          <ReportContentButton targetKind="POST" targetId={post.id} label="Report post" />
        </div>
        {showComments && (
          <div className="upper-room-post__comments">
            {comments.isPending ? <p>Loading conversation…</p> : comments.isError ? <p>Comments could not be loaded. Try again.</p> : comments.data?.length ? comments.data.map((item) => <article key={item.id}><span>{initials(item.authorName)}</span><p><strong>{item.authorName}</strong>{item.body}</p><ReportContentButton targetKind="COMMENT" targetId={item.id} label="Report comment" /></article>) : <p>Start the conversation with kindness.</p>}
            <form onSubmit={(event) => { event.preventDefault(); if (comment.trim()) addComment.mutate(); }}>
              <input value={comment} onChange={(event) => setComment(event.target.value)} maxLength={750} placeholder="Add a thoughtful comment…" aria-label="Add a comment" />
              <Button type="submit" variant="ghost" loading={addComment.isPending} icon={<Send />}>Post</Button>
            </form>
          </div>
        )}
      </article>

      {shareOpen && (
        <div className="upper-room__viewer" role="dialog" aria-modal="true" aria-label="Share this Upper Room post" onClick={() => setShareOpen(false)}>
          <div className="upper-room__share-dialog" onClick={(event) => event.stopPropagation()}>
            <header><strong>Share this moment</strong><button type="button" aria-label="Close share card" onClick={() => setShareOpen(false)}><X /></button></header>
            <div className="upper-room__share-card">
              <div className="upper-room__share-brand"><Sparkles /><span>CHAPELFLOW</span></div>
              {post.media[0] && (post.media[0].mediaType === "IMAGE"
                ? <img src={post.media[0].url} alt="" />
                : <div className="upper-room__share-video"><Video /><span>Video shared in The Upper Room</span></div>)}
              <strong>{post.authorName}</strong>
              <p>{post.caption || "A moment shared with the Chrisland University Chapel community."}</p>
              <small>THE UPPER ROOM · CHRISLAND UNIVERSITY CHAPEL</small>
            </div>
            <div className="upper-room__share-actions">
              <Button type="button" onClick={() => void share()} icon={<Share2 />}>Share</Button>
              <Button type="button" variant="secondary" onClick={() => void copyLink()} icon={<Copy />}>Copy link</Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
