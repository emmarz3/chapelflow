import { ArrowRight, FileText } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  EmptyState,
  ErrorState,
  LoadingState,
  PageHeader,
  SearchField,
} from "../components/ui";
import { publicService } from "../services/chapelflow";
import { CHAPEL_PROGRAMMES } from "../lib/chapel-programmes";
import { CalendarDays, Clock3, MapPin } from "lucide-react";
import type { EventSummary } from "../types/domain";
import { useTodayDateKey } from "../lib/use-today-date";

export function LivePublicPage({ slug }: { slug: string }) {
  if (slug === "events") return <LivePublicEventsPage />;
  return <LivePublicContentPage slug={slug} />;
}

function LivePublicContentPage({ slug }: { slug: string }) {
  const [search, setSearch] = useState("");
  const query = useQuery({
    queryKey: ["public-content", slug, search],
    queryFn: async () => (await publicService.content(slug, search)).data,
  });
  if (query.isPending)
    return (
      <div className="section">
        <LoadingState label="Loading chapel content" />
      </div>
    );
  if (query.isError)
    return (
      <div className="section">
        <ErrorState
          description={
            query.error instanceof Error
              ? query.error.message
              : "The page could not be loaded."
          }
          onRetry={() => void query.refetch()}
        />
      </div>
    );
  const content = query.data;
  return (
    <div className="content-page">
      <PageHeader
        eyebrow={content.eyebrow}
        title={content.title}
        description={content.description}
      />
      {slug === "sermons" && (
        <div className="section filter-bar" role="search">
          <SearchField
            value={search}
            onChange={setSearch}
            placeholder="Search messages, speakers, and resources"
          />
        </div>
      )}
      <div className="cms-public-sections section">
        {content.sections.map((section) => (
          <section key={section.id}>
            {section.imageUrl && section.mediaType === "video" ? (
              <video controls preload="metadata"><source src={section.imageUrl} /></video>
            ) : section.imageUrl && (
              <img
                src={section.imageUrl}
                alt={section.imageAlt || ""}
                loading="lazy"
              />
            )}
            {section.heading && <h2>{section.heading}</h2>}
            <p>{section.body}</p>
            {section.action && (
              /^https?:\/\//.test(section.action.href) ? (
                <a href={section.action.href} target="_blank" rel="noreferrer">
                  {section.action.label} <ArrowRight />
                </a>
              ) : (
                <Link to={section.action.href}>
                  {section.action.label} <ArrowRight />
                </Link>
              )
            )}
          </section>
        ))}
        {!content.sections.length && (
          <EmptyState
            icon={<FileText />}
            title="Content is being prepared"
            description="This page has been published without any visible sections."
          />
        )}
      </div>
    </div>
  );
}

function LivePublicEventsPage() {
  const today = useTodayDateKey();
  const query = useQuery({
    queryKey: ["public-events", 1, 50],
    queryFn: async () => (await publicService.events({ page: 1, pageSize: 50 })).data,
    refetchInterval: 60_000,
  });
  const publishedEvents: EventSummary[] = (query.data ?? []).filter((event) => event.date >= today);
  const eventDates = new Set(publishedEvents.map((event) => `${event.title}|${event.date}`));
  const programmes = CHAPEL_PROGRAMMES
    .filter((event) => (event.date ?? event.sortDate ?? "") >= today)
    .filter((event) => !event.date || !eventDates.has(`${event.title}|${event.date}`));
  return (
    <div className="content-page">
      <PageHeader eyebrow="Chrisland University Chapel" title="Events and programmes" description="Gather with us for worship, fellowship, and special chapel programmes." />
      <section className="public-programmes section" aria-labelledby="public-programmes-title">
        <div className="public-programmes__heading"><p className="event-type">UPCOMING PROGRAMMES</p><h2 id="public-programmes-title">Save the dates</h2><p>Programme details will be updated as they are confirmed.</p></div>
        {query.isError && <p className="public-programmes__note">Some published event details may be temporarily unavailable. The chapel schedule below is still available.</p>}
        <div className="public-programmes__grid">
          {programmes.map((event) => (
            <article className={event.id.startsWith("commanding-excellence") ? "public-programme-card public-programme-card--featured" : "public-programme-card"} key={event.id}>
              <div className="public-programme-card__date"><CalendarDays aria-hidden="true" /><time dateTime={event.date ?? undefined}>{event.displayDate ?? new Intl.DateTimeFormat("en", { weekday: "short", month: "short", day: "numeric", year: "numeric" }).format(new Date(`${event.date}T12:00:00`))}</time></div>
              <p className="event-type">{event.id.startsWith("commanding-excellence") ? "3 SUNDAYS OF COMMANDING EXCELLENCE" : "CHAPEL PROGRAMME"}</p>
              <h3>{event.title}</h3>
              {event.detail && <p className="public-programme-card__detail">{event.detail}</p>}
              <p className="public-programme-card__meta"><Clock3 aria-hidden="true" />{event.id.startsWith("commanding-excellence") ? "Weekly · 8:00 AM and 10:30 AM" : event.id.startsWith("retreat-") ? event.detail : "Time to be announced"}</p>
              <p className="public-programme-card__meta"><MapPin aria-hidden="true" />{event.venue}</p>
            </article>
          ))}
          {publishedEvents.map((event) => (
            <article className="public-programme-card" key={`published-${event.id}`}>
              <div className="public-programme-card__date"><CalendarDays aria-hidden="true" /><time dateTime={event.date}>{new Intl.DateTimeFormat("en", { weekday: "short", month: "short", day: "numeric", year: "numeric" }).format(new Date(`${event.date}T12:00:00`))}</time></div>
              <p className="event-type">CHAPEL PROGRAMME</p><h3>{event.title}</h3>
              <p className="public-programme-card__meta"><Clock3 aria-hidden="true" />{event.time || "Time to be announced"}</p>
              <p className="public-programme-card__meta"><MapPin aria-hidden="true" />{event.venue}</p>
            </article>
          ))}
          {!programmes.length && !publishedEvents.length && <p className="public-programmes__note">No upcoming chapel events are currently scheduled.</p>}
        </div>
      </section>
    </div>
  );
}

export function LivePublicDetailPage({
  kind,
}: {
  kind: "events" | "sermons" | "news" | "gallery";
}) {
  const params = useParams();
  const id =
    params.eventId ||
    params.sermonId ||
    params.articleId ||
    params.galleryId ||
    "";
  const query = useQuery({
    queryKey: ["public-detail", kind, id],
    queryFn: async () => (await publicService.detail(kind, id)).data,
    enabled: Boolean(id),
    refetchInterval: kind === "gallery" ? 5_000 : false,
  });
  if (query.isPending)
    return (
      <div className="section">
        <LoadingState />
      </div>
    );
  if (query.isError)
    return (
      <div className="section">
        <ErrorState
          title="This item is unavailable"
          description="It may be unpublished, archived, or restricted."
          onRetry={() => void query.refetch()}
        />
      </div>
    );
  return <LiveDetailContent content={query.data} />;
}

function LiveDetailContent({
  content,
}: {
  content: Awaited<ReturnType<typeof publicService.content>>["data"];
}) {
  return (
    <div className="content-page">
      <PageHeader
        eyebrow={content.eyebrow}
        title={content.title}
        description={content.description}
      />
      <article className="cms-article section">
        {content.sections.map((section) => (
          <section key={section.id}>
            {section.imageUrl && section.mediaType === "video" ? (
              <video controls preload="metadata"><source src={section.imageUrl} /></video>
            ) : section.imageUrl && (
              <img
                src={section.imageUrl}
                alt={section.imageAlt || ""}
                loading="lazy"
              />
            )}
            {section.heading && <h2>{section.heading}</h2>}
            <p>{section.body}</p>
            {section.action && (
              /^https?:\/\//.test(section.action.href) ? (
                <a className="button button--secondary" href={section.action.href} target="_blank" rel="noreferrer">
                  {section.action.label} <ArrowRight />
                </a>
              ) : (
                <Link className="button button--secondary" to={section.action.href}>
                  {section.action.label} <ArrowRight />
                </Link>
              )
            )}
          </section>
        ))}
      </article>
    </div>
  );
}
