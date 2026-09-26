import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Camera, Image, Play, PlayCircle } from "lucide-react";
import { Link } from "react-router-dom";
import { EmptyState, ErrorState, LoadingState } from "../components/ui";
import { isDemoMode } from "../lib/fixtures";
import { publicService } from "../services/chapelflow";

const previewAlbums = [
  { id: "last-semester-worship", title: "Last semester in worship", body: "Services, worship nights, and shared moments from the chapel community.", imageUrl: "/chapel-hero.jpg" },
  { id: "community-in-motion", title: "Community in motion", body: "Fellowship, service, and life beyond the lecture hall.", imageUrl: "/chapelflow-auth-register-visual.png" },
];

export function GalleryPage() {
  const gallery = useQuery({ queryKey: ["public-content", "gallery"], queryFn: async () => (await publicService.content("gallery")).data, enabled: !isDemoMode, refetchInterval: isDemoMode ? false : 5_000 });
  if (!isDemoMode && gallery.isPending) return <div className="section"><LoadingState label="Opening the chapel gallery" /></div>;
  if (!isDemoMode && gallery.isError) return <div className="section"><ErrorState description="The gallery could not be loaded. Please try again." onRetry={() => void gallery.refetch()} /></div>;
  const albums = isDemoMode ? previewAlbums : (gallery.data?.sections ?? []).map((item) => ({ id: item.id, title: item.heading || "Chapel moments", body: item.body, imageUrl: item.imageUrl || "/chapel-hero.jpg", href: item.action?.href || `/gallery/${item.id}` }));
  const featured = albums[0];
  const remaining = albums.slice(1);
  return <div className="chapel-gallery">
    <section className="chapel-gallery__hero">
      <div className="chapel-gallery__hero-copy"><p className="eyebrow">Chrisland University Chapel · Official media</p><h1>Life together, <em>in frames.</em></h1><p>Worship, fellowship, service, and the small moments that make chapel feel like home.</p><div className="chapel-gallery__hero-meta"><span><Camera /> Curated by the chapel media team</span><span>Updated each semester</span></div></div>
      <div className="chapel-gallery__hero-art"><img src="/chapel-hero.jpg" alt="Students gathering at Chrisland University Chapel" /><span>01 / 04</span></div>
    </section>
    <main className="chapel-gallery__content">
      <header className="chapel-gallery__heading"><div><p className="eyebrow">The archive</p><h2>Recent collections</h2></div><p>Official photographs and videos, published with care and consent.</p></header>
      {featured ? <Link className="chapel-gallery__featured" to={("href" in featured && featured.href) || `/gallery/${featured.id}`}><img src={featured.imageUrl} alt="" /><div className="chapel-gallery__featured-copy"><span>Featured collection · 01</span><h3>{featured.title}</h3><p>{featured.body}</p><strong>Explore collection <ArrowRight /></strong></div></Link> : null}
      {remaining.length ? <div className="chapel-gallery__grid">{remaining.map((album, index) => <Link key={album.id} to={("href" in album && album.href) || `/gallery/${album.id}`} className={`chapel-gallery__album chapel-gallery__album--${index % 2 ? "tall" : "standard"}`}><div className="chapel-gallery__album-image"><img src={album.imageUrl} alt="" loading="lazy" /><span><Image /> Collection</span></div><div><h3>{album.title}</h3><p>{album.body}</p><strong>View album <ArrowRight /></strong></div></Link>)}</div> : !featured ? <EmptyState icon={<PlayCircle />} title="The gallery is being prepared" description="Official chapel media will appear here after it has been reviewed and published." /> : null}
      <section className="chapel-gallery__note"><Play /><div><strong>More moments are on the way.</strong><p>Official media uploads are reviewed before they appear in the public gallery.</p></div></section>
    </main>
  </div>;
}
