import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Heart, Home, ImagePlus, MessageCircle, PlusSquare, Search, Send, Sparkles, Trash2, Video, X, Share2 } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useEffect, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { Button, EmptyState, ErrorState, LoadingState, useToast } from "../components/ui";
import { upperRoomService, type UpperRoomPost } from "../services/chapelflow";
import { useAuth } from "./auth-context";
import { ReportContentButton } from "./moderation";
import { prepareSocialMedia } from "../lib/media-compress";
import { getRecentUpperRoomPosts, saveRecentUpperRoomPost } from "../lib/upper-room-media-cache";
import { createUpperRoomShareFile, downloadShareImage } from "../lib/upper-room-share";

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
  jpg: "image/jpeg",
  jpeg: "image/jpeg",
  png: "image/png",
  gif: "image/gif",
  webp: "image/webp",
  mp4: "video/mp4",
  mov: "video/quicktime",
  webm: "video/webm",
};

function mediaFileError(file: File) {
  const extension = file.name.includes(".") ? file.name.split(".").pop()!.toLowerCase() : "";
  if (!UPPER_ROOM_MEDIA_TYPES[extension] || file.type !== UPPER_ROOM_MEDIA_TYPES[extension]) {
    return `${file.name}: use JPG, PNG, GIF, WebP, MP4, MOV, or WebM media.`;
  }
  if (file.size > 50 * 1024 * 1024) {
    return `${file.name}: the maximum file size is 50 MB.`;
  }
  return null;
}

export function UpperRoomPage() {
  const { user } = useAuth();
  const toast = useToast();
  const client = useQueryClient();
  const [caption, setCaption] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [selectedBranch, setSelectedBranch] = useState("");
  const [showIntro, setShowIntro] = useState(() => {
    try { return sessionStorage.getItem("chapelflow:upper-room-intro") !== "1"; } catch { return true; }
  });
  const [storyFile, setStoryFile] = useState<File | null>(null);
  const [activeStory, setActiveStory] = useState<UpperRoomPost | null>(null);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [recentOpen, setRecentOpen] = useState(false);
  const [params, setParams] = useSearchParams();
  const reduceMotion = useReducedMotion();
  const feed = useQuery({ queryKey: ["upper-room", page], queryFn: async () => (await upperRoomService.feed(page)).data });
  const stories = useQuery({ queryKey: ["upper-room-stories"], queryFn: async () => (await upperRoomService.stories()).data });
  const sharedId = params.get("post") || "";
  const shared = useQuery({ queryKey: ["upper-room-shared", sharedId], queryFn: async () => (await upperRoomService.post(sharedId)).data, enabled: Boolean(sharedId), retry: false });
  const recentKey = `chapelflow:recent-media:${user?.id ?? "anonymous"}`;
  const [recentIds, setRecentIds] = useState<string[]>(() => {
    try { return JSON.parse(localStorage.getItem(recentKey) || "[]") as string[]; } catch { return []; }
  });
  const [recentCachedPosts, setRecentCachedPosts] = useState<UpperRoomPost[]>([]);
  const [recentLoading, setRecentLoading] = useState(false);
  useEffect(() => {
    try { setRecentIds(JSON.parse(localStorage.getItem(recentKey) || "[]") as string[]); }
    catch { setRecentIds([]); }
  }, [recentKey]);
  useEffect(() => {
    if (!recentOpen || !user?.id) {
      setRecentCachedPosts([]);
      return;
    }
    let active = true;
    const objectUrls: string[] = [];
    async function loadRecentMedia() {
      setRecentLoading(true);
      try {
        let cached = await getRecentUpperRoomPosts(user.id);
        const cachedIds = new Set(cached.map((item) => item.post.id));
        if (navigator.onLine) {
          for (const id of recentIds.slice(0, 12)) {
            if (cachedIds.has(id)) continue;
            try {
              const post = (await upperRoomService.post(id)).data;
              await saveRecentUpperRoomPost(user.id, post);
            } catch {
              // Older recent-media entries may no longer be accessible.
            }
          }
          cached = await getRecentUpperRoomPosts(user.id);
        }
        const posts = cached.map((record) => ({
          ...record.post,
          media: record.post.media.map((item) => {
            const blob = record.media.find((cachedItem) => cachedItem.id === item.id)?.blob;
            if (!blob) return { ...item, url: "" };
            const url = URL.createObjectURL(blob);
            objectUrls.push(url);
            return { ...item, url };
          }),
        }));
        if (active) setRecentCachedPosts(posts);
      } catch {
        if (active) setRecentCachedPosts([]);
      } finally {
        if (active) setRecentLoading(false);
      }
    }
    void loadRecentMedia();
    return () => {
      active = false;
      objectUrls.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [recentOpen, user?.id, recentIds]);
  function remember(post: UpperRoomPost) {
    if (!post.media.length || post.isStory || !user?.id) return;
    const updated = [post.id, ...recentIds.filter((id) => id !== post.id)].slice(0, 12);
    setRecentIds(updated);
    try { localStorage.setItem(recentKey, JSON.stringify(updated)); } catch { /* Recent IDs are optional; media caching still works. */ }
    void saveRecentUpperRoomPost(user.id, post).then((result) => {
      if (result.cachedCount > 0) toast(result.cachedCount === result.mediaCount
        ? "This post is saved for offline viewing."
        : "Some media could not be saved for offline viewing.");
    }).catch(() => toast("This media could not be saved for offline viewing.", "error"));
  }
  const publishStory = useMutation({ mutationFn: async () => upperRoomService.createStory((await prepareSocialMedia([storyFile!]))[0]!, "", selectedBranch || undefined), onSuccess: () => { setStoryFile(null); toast("Your story is live for 24 hours."); void client.invalidateQueries({ queryKey: ["upper-room-stories"] }); }, onError: (error) => toast(failureMessage(error), "error") });
  useEffect(() => {
    if (!showIntro) return;
    const timer = window.setTimeout(() => {
      try { sessionStorage.setItem("chapelflow:upper-room-intro", "1"); } catch { /* Storage may be unavailable. */ }
      setShowIntro(false);
    }, reduceMotion ? 0 : 850);
    return () => window.clearTimeout(timer);
  }, [reduceMotion, showIntro]);
  const publish = useMutation({
    mutationFn: async () => upperRoomService.createPost(caption.trim(), await prepareSocialMedia(files), selectedBranch || undefined),
    onSuccess: () => {
      setCaption("");
      setFiles([]);
      toast("Shared in The Upper Room.");
      void client.invalidateQueries({ queryKey: ["upper-room"] });
    },
    onError: (error) => toast(failureMessage(error), "error"),
  });

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
    if (files.reduce((size, file) => size + file.size, 0) > 50 * 1024 * 1024) {
      toast("A post can contain up to 50 MB of photos and videos in total.", "error");
      return;
    }
    publish.mutate();
  }

  const posts = feed.data?.items ?? [];
  const shownPosts = posts.filter((post) => `${post.authorName} ${post.caption}`.toLowerCase().includes(search.toLowerCase()));
  function goHome() {
    setPage(1);
    setRecentOpen(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
  return (
    <div className="upper-room">
      <AnimatePresence>
        {showIntro && <motion.div className="upper-room__intro-screen" initial={{ opacity: 1 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: reduceMotion ? 0 : 0.45 }} aria-label="Opening The Upper Room">
          <motion.div className="upper-room__intro-symbol" initial={{ scale: 0.7, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ duration: reduceMotion ? 0 : 0.55 }}><Sparkles /></motion.div>
          <motion.p initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: reduceMotion ? 0 : 0.18, duration: reduceMotion ? 0 : 0.5 }}>The Upper Room</motion.p>
          <motion.span initial={{ scaleX: 0 }} animate={{ scaleX: 1 }} transition={{ delay: reduceMotion ? 0 : 0.32, duration: reduceMotion ? 0 : 0.55 }} />
        </motion.div>}
      </AnimatePresence>
      <header className="upper-room__topbar">
        <div className="upper-room__brand"><span className="upper-room__brand-mark" aria-hidden="true"><Sparkles /></span><strong>The Upper Room</strong></div>
        <label className="upper-room__search"><Search /><input aria-label="Search The Upper Room" placeholder="Search" value={search} onChange={(event) => setSearch(event.target.value)} /></label>
        <nav aria-label="Upper Room actions"><button type="button" aria-label="Home" onClick={goHome}><Home /></button><button type="button" aria-label="Create a post" onClick={() => document.getElementById("upper-room-caption")?.focus()}><PlusSquare /></button><button type="button" onClick={() => setRecentOpen((open) => !open)}>Recent media</button></nav>
      </header>
      <div className="upper-room__layout">
        <main className="upper-room__main">
          <section className="upper-room__stories" aria-label="Upper Room stories"><label className="upper-room__story"><span className="upper-room__story-ring"><span><ImagePlus /></span></span><small>Add story</small><input type="file" accept="image/jpeg,image/png,image/gif,image/webp,video/mp4,video/quicktime,video/webm" hidden onChange={(event) => { const file = event.target.files?.[0]; if (!file) return; const invalid = mediaFileError(file); if (invalid) toast(invalid, "error"); else setStoryFile(file); event.target.value = ""; }} /></label>{stories.data?.items.map((story, index) => <button type="button" key={story.id} className="upper-room__story" onClick={() => setActiveStory(story)}><span className={`upper-room__story-ring upper-room__story-ring--${index % 3}`}><span>{initials(story.authorName)}</span></span><small>{story.authorName.split(" ")[0]}</small></button>)}</section>
          {stories.isError && <p role="alert">Stories could not be loaded. <button type="button" onClick={() => void stories.refetch()}>Try again</button></p>}
          {storyFile && <section className="panel"><p>Share {storyFile.name} as a 24-hour story?</p>{user?.role === "super_admin" && <label>Branch <select value={selectedBranch} onChange={(event) => setSelectedBranch(event.target.value)}><option value="">Select branch</option>{feed.data?.branches.map((branch) => <option key={branch.id} value={branch.id}>{branch.name}</option>)}</select></label>}{publishStory.isPending && <p role="status">Uploading your story… Keep this page open; mobile video uploads can take a minute.</p>}<Button loading={publishStory.isPending} disabled={publishStory.isPending || (user?.role === "super_admin" && !selectedBranch)} onClick={() => publishStory.mutate()}>Post story</Button><Button variant="ghost" disabled={publishStory.isPending} onClick={() => setStoryFile(null)}>Cancel</Button></section>}
          {activeStory && <section className="upper-room__story-view panel" role="dialog" aria-label="Story"><Button variant="ghost" onClick={() => setActiveStory(null)}>Close story</Button><h2>{activeStory.authorName}</h2>{activeStory.media[0]?.mediaType === "VIDEO" ? <video controls playsInline src={activeStory.media[0].url} /> : <img src={activeStory.media[0]?.url} alt={`Story by ${activeStory.authorName}`} />}</section>}
          {sharedId && <section className="panel"><Button variant="ghost" onClick={() => { params.delete("post"); setParams(params); }}>Close shared post</Button>{shared.isPending ? <LoadingState label="Opening shared post" /> : shared.isError ? <ErrorState description="This post is unavailable or outside your chapel branch." /> : shared.data && <PostCard post={shared.data} onOpen={remember} />}</section>}
          {recentOpen && <section className="panel"><h2>Recently opened media</h2><p>Photos and videos you opened are saved privately on this device. They can be reopened without a connection while you remain signed in.</p>{recentLoading ? <LoadingState label="Loading saved media" /> : recentCachedPosts.length ? recentCachedPosts.map((post) => <PostCard key={post.id} post={post} onOpen={remember} />) : <EmptyState title="No saved media yet" description="Open a photo or video while connected to save an offline copy here." />}</section>}
          <section className="upper-room__composer panel" aria-label="Create an Upper Room post">
            <div className="upper-room__avatar" aria-hidden="true">{user?.photoUrl ? <img src={user.photoUrl} alt="" /> : initials(user?.name || "")}</div>
            <form onSubmit={submit}>
              {user?.role === "super_admin" && <label className="upper-room__branch-picker">Post to chapel branch
                <select value={selectedBranch} onChange={(event) => setSelectedBranch(event.target.value)} required>
                  <option value="">Select a branch</option>
                  {(feed.data?.branches ?? []).map((branch) => <option key={branch.id} value={branch.id}>{branch.name}</option>)}
                </select>
              </label>}
              <label className="sr-only" htmlFor="upper-room-caption">Share with The Upper Room</label>
              <textarea id="upper-room-caption" value={caption} onChange={(event) => setCaption(event.target.value)} maxLength={1000} rows={3} placeholder="Share a thought, a praise report, or a moment from chapel…" />
              {files.length > 0 && <div className="upper-room__files">{files.map((file, index) => <span key={`${file.name}-${index}`}><Video aria-hidden="true" /> {file.name}<button type="button" aria-label={`Remove ${file.name}`} onClick={() => setFiles((items) => items.filter((_, itemIndex) => itemIndex !== index))}><X /></button></span>)}</div>}
              <div className="upper-room__composer-actions"><label className="upper-room__file-picker"><ImagePlus /> Add photos or videos<input type="file" accept=".jpg,.jpeg,.png,.gif,.webp,.mp4,.mov,.webm,image/jpeg,image/png,image/gif,image/webp,video/mp4,video/quicktime,video/webm" multiple onChange={(event) => {
                const selected = Array.from(event.currentTarget.files ?? []);
                event.currentTarget.value = "";
                if (selected.length > 4) {
                  toast("Add up to four photos or videos in one post.", "error");
                  return;
                }
                const invalid = selected.map(mediaFileError).find(Boolean);
                if (invalid) {
                  toast(invalid, "error");
                  return;
                }
                if (selected.reduce((size, file) => size + file.size, 0) > 50 * 1024 * 1024) {
                  toast("A post can contain up to 50 MB of photos and videos in total.", "error");
                  return;
                }
                setFiles(selected);
              }} /></label><small>JPG, PNG, GIF, WebP, MP4, MOV or WebM · 50 MB total per post</small><Button type="submit" loading={publish.isPending} icon={<Send />}>Share</Button></div>
            </form>
          </section>
          <section className="upper-room__feed" aria-label="Upper Room posts">
            {feed.isPending ? <LoadingState label="Loading Upper Room posts" /> : feed.isError ? <ErrorState description={failureMessage(feed.error)} onRetry={() => void feed.refetch()} /> : shownPosts.length ? shownPosts.map((post) => <PostCard key={post.id} post={post} onOpen={remember} />) : <EmptyState icon={<MessageCircle />} title={search ? "No matching posts" : "The room is ready"} description="Try another search or share a moment with your chapel community." />}
            {!feed.isPending && !feed.isError && <div className="upper-room__pagination"><Button variant="ghost" disabled={page === 1} onClick={() => setPage((current) => current - 1)}>Previous</Button><span>Page {page}</span><Button variant="ghost" disabled={!feed.data?.hasMore} onClick={() => setPage((current) => current + 1)}>Load more</Button></div>}
          </section>
        </main>
        <aside className="upper-room__sidebar"><div className="upper-room__profile"><div className="upper-room__avatar">{user?.photoUrl ? <img src={user.photoUrl} alt="" /> : initials(user?.name || "")}</div><div><strong>{user?.name || "Chapel member"}</strong><small>Chrisland University Chapel</small></div></div><div className="upper-room__suggestions"><header><strong>Recently opened</strong><button type="button" onClick={() => setRecentOpen(true)}>See all</button></header><p>Revisit media you opened on this device.</p><span><Sparkles /> Share with care. Keep the grace.</span></div></aside>
      </div>
      <nav className="upper-room__mobile-nav" aria-label="Upper Room mobile navigation"><button type="button" aria-label="Home" onClick={goHome}><Home /></button><button type="button" aria-label="Search" onClick={() => document.querySelector<HTMLInputElement>(".upper-room__search input")?.focus()}><Search /></button><button type="button" aria-label="Create a post" onClick={() => document.getElementById("upper-room-caption")?.focus()}><PlusSquare /></button><button type="button" onClick={() => setRecentOpen((open) => !open)}>Recent</button><span className="upper-room__avatar" aria-hidden="true">{user?.photoUrl ? <img src={user.photoUrl} alt="" /> : initials(user?.name || "")}</span></nav>
    </div>
  );
}

function PostCard({ post, onOpen }: { post: UpperRoomPost; onOpen?: (post: UpperRoomPost) => void }) {
  const { user } = useAuth();
  const toast = useToast();
  const client = useQueryClient();
  const [showComments, setShowComments] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);
  const [comment, setComment] = useState("");
  const [shareImageUrl, setShareImageUrl] = useState("");
  const [shareBusy, setShareBusy] = useState(false);
  useEffect(() => () => {
    if (shareImageUrl) URL.revokeObjectURL(shareImageUrl);
  }, [shareImageUrl]);
  const comments = useQuery({ queryKey: ["upper-room-comments", post.id], queryFn: async () => (await upperRoomService.comments(post.id)).data, enabled: showComments });
  const like = useMutation({ mutationFn: () => upperRoomService.toggleLike(post.id), onSuccess: () => void client.invalidateQueries({ queryKey: ["upper-room"] }), onError: (error) => toast(failureMessage(error), "error") });
  const remove = useMutation({ mutationFn: () => upperRoomService.deletePost(post.id), onSuccess: () => { toast("Post removed."); void client.invalidateQueries({ queryKey: ["upper-room"] }); }, onError: (error) => toast(failureMessage(error), "error") });
  const addComment = useMutation({ mutationFn: () => upperRoomService.createComment(post.id, comment.trim()), onSuccess: () => { setComment(""); void client.invalidateQueries({ queryKey: ["upper-room-comments", post.id] }); void client.invalidateQueries({ queryKey: ["upper-room"] }); }, onError: (error) => toast(failureMessage(error), "error") });
  const isOwnPost = post.authorName === user?.name;
  const canModerate = ["super_admin", "chapel_admin", "chaplain", "student_chaplain"].includes(user?.role ?? "");
  const postUrl = `${window.location.origin}/app/upper-room?post=${encodeURIComponent(post.id)}`;
  async function generateShareImage() {
    setShareBusy(true);
    try {
      const file = await createUpperRoomShareFile(post);
      setShareImageUrl(URL.createObjectURL(file));
      toast("Your shareable image card is ready.");
    } catch (error) {
      toast(failureMessage(error), "error");
    } finally {
      setShareBusy(false);
    }
  }
  async function share() {
    setShareBusy(true);
    try {
      const file = await createUpperRoomShareFile(post);
      setShareImageUrl(URL.createObjectURL(file));
      const shareData = {
        title: `${post.authorName} · The Upper Room`,
        text: (post.caption || "A chapel moment") + `\n\nOpen in ChapelFlow: ${postUrl}`,
        url: postUrl,
        files: [file],
      };
      const canShareFile = typeof navigator.share === "function" &&
        typeof navigator.canShare === "function" && navigator.canShare({ files: [file] });
      if (canShareFile) {
        await navigator.share(shareData);
      } else {
        downloadShareImage(file);
        try {
          await navigator.clipboard.writeText(postUrl);
          toast("Image card downloaded and the private post link copied.");
        } catch {
          toast("Image card downloaded. Copy the post link from the Share panel to send it with the image.");
        }
      }
    } catch (error) {
      if ((error as DOMException).name !== "AbortError") toast(failureMessage(error), "error");
    } finally {
      setShareBusy(false);
    }
  }
  async function downloadCard() {
    setShareBusy(true);
    try {
      const file = await createUpperRoomShareFile(post);
      setShareImageUrl(URL.createObjectURL(file));
      downloadShareImage(file);
      toast("Shareable image card downloaded.");
    } catch (error) {
      toast(failureMessage(error), "error");
    } finally {
      setShareBusy(false);
    }
  }
  return <article className="upper-room-post panel">
    <header><div className="upper-room__avatar" aria-hidden="true">{initials(post.authorName)}</div><div><strong>{post.authorName}</strong><small>{relativeTime(post.createdAt)} · {post.branchName || "The Upper Room"}</small></div>{(isOwnPost || canModerate) && <button className="icon-button" type="button" aria-label="Remove post" disabled={remove.isPending} onClick={() => { if (window.confirm("Remove this post from The Upper Room?")) remove.mutate(); }}><Trash2 /></button>}</header>
    {post.caption && <p className="upper-room-post__caption">{post.caption}</p>}
    {post.media.length > 0 && <div className={`upper-room-post__media upper-room-post__media--${Math.min(post.media.length, 4)}`} onClick={() => onOpen?.(post)}>{post.media.map((media) => !media.url ? <div key={media.id} className="upper-room-post__offline-placeholder" role="img" aria-label="This media was not saved for offline viewing">Not saved offline</div> : media.mediaType === "VIDEO" ? <video key={media.id} controls preload="metadata" playsInline onPlay={() => onOpen?.(post)}><source src={media.url} /></video> : <img key={media.id} src={media.url} alt="Shared Upper Room post" loading="lazy" />)}</div>}
    <div className="upper-room-post__counts"><span>{post.likeCount ? `${post.likeCount} ${post.likeCount === 1 ? "like" : "likes"}` : "Be the first to like this"}</span><button type="button" onClick={() => setShowComments((open) => !open)}>{post.commentCount ? `${post.commentCount} ${post.commentCount === 1 ? "comment" : "comments"}` : "Comment"}</button></div>
    <div className="upper-room-post__actions"><button type="button" className={post.isLiked ? "is-liked" : ""} disabled={like.isPending} onClick={() => like.mutate()}><Heart fill={post.isLiked ? "currentColor" : "none"} /> {post.isLiked ? "Liked" : "Like"}</button><button type="button" onClick={() => setShowComments((open) => !open)}><MessageCircle /> Comment</button><button type="button" onClick={() => setShareOpen((open) => !open)}><Share2 /> Share</button><ReportContentButton targetKind="POST" targetId={post.id} label="Report post" /></div>
    {shareOpen && <div className="upper-room__share-panel"><div className="upper-room__share-card">{post.media.find((item) => item.mediaType === "IMAGE")?.url && <img src={post.media.find((item) => item.mediaType === "IMAGE")!.url} alt="Shared post preview" />}<div><small>CHAPELFLOW · THE UPPER ROOM</small><strong>{post.caption || "A chapel moment"}</strong><span>{post.authorName} · {post.branchName}</span></div></div>{shareImageUrl && <img className="upper-room__share-image-preview" src={shareImageUrl} alt="Generated ChapelFlow share image card" />}<p>The generated image can be shared as a picture. Its link opens the original post, which is available to signed-in chapel members only.</p><div className="upper-room__share-actions"><Button variant="secondary" disabled={shareBusy} loading={shareBusy} onClick={() => void generateShareImage()}>{shareImageUrl ? "Regenerate image card" : "Generate image card"}</Button><Button disabled={shareBusy} loading={shareBusy} onClick={() => void share()}><Share2 /> Share image card</Button><Button variant="ghost" disabled={shareBusy} onClick={() => void downloadCard()}>Download image</Button><Button variant="ghost" onClick={() => void navigator.clipboard.writeText(postUrl).then(() => toast("Private post link copied."), () => toast("Could not copy the post link.", "error"))}>Copy post link</Button></div></div>}
    {showComments && <div className="upper-room-post__comments">{comments.isPending ? <p>Loading conversation…</p> : comments.isError ? <p>Comments could not be loaded. Try again.</p> : comments.data?.length ? comments.data.map((item) => <article key={item.id}><span>{initials(item.authorName)}</span><p><strong>{item.authorName}</strong>{item.body}</p><ReportContentButton targetKind="COMMENT" targetId={item.id} label="Report comment" /></article>) : <p>Start the conversation with kindness.</p>}<form onSubmit={(event) => { event.preventDefault(); if (comment.trim()) addComment.mutate(); }}><input value={comment} onChange={(event) => setComment(event.target.value)} maxLength={750} placeholder="Add a thoughtful comment…" aria-label="Add a comment" /><Button type="submit" variant="ghost" loading={addComment.isPending} icon={<Send />}>Post</Button></form></div>}
  </article>;
}
