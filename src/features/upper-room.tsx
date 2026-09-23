import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, Compass, Heart, Home, ImagePlus, MessageCircle, PlusSquare, Search, Send, Sparkles, Trash2, Video, X } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useEffect, useState, type FormEvent } from "react";
import { Button, EmptyState, ErrorState, LoadingState, useToast } from "../components/ui";
import { upperRoomService, type UpperRoomPost } from "../services/chapelflow";
import { useAuth } from "./auth-context";

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

export function UpperRoomPage() {
  const { user } = useAuth();
  const toast = useToast();
  const client = useQueryClient();
  const [caption, setCaption] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [showIntro, setShowIntro] = useState(true);
  const reduceMotion = useReducedMotion();
  const feed = useQuery({ queryKey: ["upper-room", 1], queryFn: async () => (await upperRoomService.feed()).data });
  useEffect(() => {
    const timer = window.setTimeout(() => setShowIntro(false), reduceMotion ? 500 : 1700);
    return () => window.clearTimeout(timer);
  }, [reduceMotion]);
  const publish = useMutation({
    mutationFn: () => upperRoomService.createPost(caption.trim(), files),
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
    if (!caption.trim() && !files.length) {
      toast("Add a caption, photo, or video before sharing.", "error");
      return;
    }
    publish.mutate();
  }

  if (feed.isPending) return <LoadingState label="Opening The Upper Room" />;
  if (feed.isError) return <ErrorState description={failureMessage(feed.error)} onRetry={() => void feed.refetch()} />;
  const posts = feed.data?.items ?? [];
  const storyNames = Array.from(new Set([user?.name || "You", ...posts.map((post) => post.authorName)])).slice(0, 7);
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
        <label className="upper-room__search"><Search /><input aria-label="Search The Upper Room" placeholder="Search" /></label>
        <nav aria-label="Upper Room actions"><button type="button" aria-label="Home"><Home /></button><button type="button" aria-label="Create a post" onClick={() => document.getElementById("upper-room-caption")?.focus()}><PlusSquare /></button><button type="button" aria-label="Explore"><Compass /></button><button type="button" aria-label="Notifications"><Bell /></button><button type="button" aria-label="Messages"><MessageCircle /></button></nav>
      </header>
      <div className="upper-room__layout">
        <main className="upper-room__main">
          <section className="upper-room__stories" aria-label="Upper Room stories">{storyNames.map((name, index) => <button type="button" key={name} className="upper-room__story"><span className={`upper-room__story-ring upper-room__story-ring--${index % 3}`}><span>{initials(name)}</span></span><small>{name === user?.name ? "Your story" : name.split(" ")[0]}</small></button>)}</section>
          <section className="upper-room__composer panel" aria-label="Create an Upper Room post">
            <div className="upper-room__avatar" aria-hidden="true">{initials(user?.name || "")}</div>
            <form onSubmit={submit}>
              <label className="sr-only" htmlFor="upper-room-caption">Share with The Upper Room</label>
              <textarea id="upper-room-caption" value={caption} onChange={(event) => setCaption(event.target.value)} maxLength={1000} rows={3} placeholder="Share a thought, a praise report, or a moment from chapel…" />
              {files.length > 0 && <div className="upper-room__files">{files.map((file, index) => <span key={`${file.name}-${index}`}><Video aria-hidden="true" /> {file.name}<button type="button" aria-label={`Remove ${file.name}`} onClick={() => setFiles((items) => items.filter((_, itemIndex) => itemIndex !== index))}><X /></button></span>)}</div>}
              <div className="upper-room__composer-actions"><label className="upper-room__file-picker"><ImagePlus /> Add photos or videos<input type="file" accept="image/*,video/*" multiple onChange={(event) => setFiles(Array.from(event.target.files ?? []).slice(0, 4))} /></label><small>Up to four files · 100 MB each</small><Button type="submit" loading={publish.isPending} icon={<Send />}>Share</Button></div>
            </form>
          </section>
          <section className="upper-room__feed" aria-label="Upper Room posts">
            {posts.length ? posts.map((post) => <PostCard key={post.id} post={post} />) : <EmptyState icon={<MessageCircle />} title="The room is ready" description="Be the first person in your chapel community to share a photo, video, or encouraging word." />}
          </section>
        </main>
        <aside className="upper-room__sidebar"><div className="upper-room__profile"><div className="upper-room__avatar">{initials(user?.name || "")}</div><div><strong>{user?.name || "Chapel member"}</strong><small>Chrisland University Chapel</small></div><button type="button">Switch</button></div><div className="upper-room__suggestions"><header><strong>Suggested for you</strong><button type="button">See all</button></header><p>Follow the moments and people making chapel life meaningful.</p><span><Sparkles /> Share with care. Keep the grace.</span></div></aside>
      </div>
      <nav className="upper-room__mobile-nav" aria-label="Upper Room mobile navigation"><button type="button" aria-label="Home"><Home /></button><button type="button" aria-label="Search"><Search /></button><button type="button" aria-label="Create a post" onClick={() => document.getElementById("upper-room-caption")?.focus()}><PlusSquare /></button><button type="button" aria-label="Notifications"><Heart /></button><span className="upper-room__avatar" aria-hidden="true">{initials(user?.name || "")}</span></nav>
    </div>
  );
}

function PostCard({ post }: { post: UpperRoomPost }) {
  const { user } = useAuth();
  const toast = useToast();
  const client = useQueryClient();
  const [showComments, setShowComments] = useState(false);
  const [comment, setComment] = useState("");
  const comments = useQuery({ queryKey: ["upper-room-comments", post.id], queryFn: async () => (await upperRoomService.comments(post.id)).data, enabled: showComments });
  const like = useMutation({ mutationFn: () => upperRoomService.toggleLike(post.id), onSuccess: () => void client.invalidateQueries({ queryKey: ["upper-room"] }), onError: (error) => toast(failureMessage(error), "error") });
  const remove = useMutation({ mutationFn: () => upperRoomService.deletePost(post.id), onSuccess: () => { toast("Post removed."); void client.invalidateQueries({ queryKey: ["upper-room"] }); }, onError: (error) => toast(failureMessage(error), "error") });
  const addComment = useMutation({ mutationFn: () => upperRoomService.createComment(post.id, comment.trim()), onSuccess: () => { setComment(""); void client.invalidateQueries({ queryKey: ["upper-room-comments", post.id] }); void client.invalidateQueries({ queryKey: ["upper-room"] }); }, onError: (error) => toast(failureMessage(error), "error") });
  const isOwnPost = post.authorName === user?.name;
  const canModerate = ["super_admin", "chapel_admin", "chaplain", "student_chaplain"].includes(user?.role ?? "");
  return <article className="upper-room-post panel">
    <header><div className="upper-room__avatar" aria-hidden="true">{initials(post.authorName)}</div><div><strong>{post.authorName}</strong><small>{relativeTime(post.createdAt)} · The Upper Room</small></div>{(isOwnPost || canModerate) && <button className="icon-button" type="button" aria-label="Remove post" disabled={remove.isPending} onClick={() => { if (window.confirm("Remove this post from The Upper Room?")) remove.mutate(); }}><Trash2 /></button>}</header>
    {post.caption && <p className="upper-room-post__caption">{post.caption}</p>}
    {post.media.length > 0 && <div className={`upper-room-post__media upper-room-post__media--${Math.min(post.media.length, 4)}`}>{post.media.map((media) => media.mediaType === "VIDEO" ? <video key={media.id} controls preload="metadata"><source src={media.url} /></video> : <img key={media.id} src={media.url} alt="Shared Upper Room post" loading="lazy" />)}</div>}
    <div className="upper-room-post__counts"><span>{post.likeCount ? `${post.likeCount} ${post.likeCount === 1 ? "like" : "likes"}` : "Be the first to like this"}</span><button type="button" onClick={() => setShowComments((open) => !open)}>{post.commentCount ? `${post.commentCount} ${post.commentCount === 1 ? "comment" : "comments"}` : "Comment"}</button></div>
    <div className="upper-room-post__actions"><button type="button" className={post.isLiked ? "is-liked" : ""} disabled={like.isPending} onClick={() => like.mutate()}><Heart fill={post.isLiked ? "currentColor" : "none"} /> {post.isLiked ? "Liked" : "Like"}</button><button type="button" onClick={() => setShowComments((open) => !open)}><MessageCircle /> Comment</button></div>
    {showComments && <div className="upper-room-post__comments">{comments.isPending ? <p>Loading conversation…</p> : comments.isError ? <p>Comments could not be loaded. Try again.</p> : comments.data?.length ? comments.data.map((item) => <article key={item.id}><span>{initials(item.authorName)}</span><p><strong>{item.authorName}</strong>{item.body}</p></article>) : <p>Start the conversation with kindness.</p>}<form onSubmit={(event) => { event.preventDefault(); if (comment.trim()) addComment.mutate(); }}><input value={comment} onChange={(event) => setComment(event.target.value)} maxLength={750} placeholder="Add a thoughtful comment…" aria-label="Add a comment" /><Button type="submit" variant="ghost" loading={addComment.isPending} icon={<Send />}>Post</Button></form></div>}
  </article>;
}
