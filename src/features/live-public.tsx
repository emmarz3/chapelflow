import { ArrowRight, FileText } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import {
  EmptyState,
  ErrorState,
  LoadingState,
  PageHeader,
} from "../components/ui";
import { publicService } from "../services/chapelflow";

export function LivePublicPage({ slug }: { slug: string }) {
  const query = useQuery({
    queryKey: ["public-content", slug],
    queryFn: async () => (await publicService.content(slug)).data,
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
      <div className="cms-public-sections section">
        {content.sections.map((section) => (
          <section key={section.id}>
            {section.imageUrl && (
              <img
                src={section.imageUrl}
                alt={section.imageAlt || ""}
                loading="lazy"
              />
            )}
            {section.heading && <h2>{section.heading}</h2>}
            <p>{section.body}</p>
            {section.action && (
              <Link to={section.action.href}>
                {section.action.label} <ArrowRight />
              </Link>
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

export function LivePublicDetailPage({
  kind,
}: {
  kind: "events" | "sermons" | "news";
}) {
  const params = useParams();
  const id = params.eventId || params.sermonId || params.articleId || "";
  const query = useQuery({
    queryKey: ["public-detail", kind, id],
    queryFn: async () => (await publicService.detail(kind, id)).data,
    enabled: Boolean(id),
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
            {section.imageUrl && (
              <img
                src={section.imageUrl}
                alt={section.imageAlt || ""}
                loading="lazy"
              />
            )}
            {section.heading && <h2>{section.heading}</h2>}
            <p>{section.body}</p>
          </section>
        ))}
      </article>
    </div>
  );
}
