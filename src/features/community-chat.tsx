import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MessageSquareText, Search, Send, ShieldCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Button, EmptyState, ErrorState, LoadingState } from "../components/ui";
import { isDjangoBackend } from "../lib/backend";
import { communityService } from "../services/chapelflow";
import type { CommunityMessage } from "../types/domain";
import { useAuth } from "./auth-context";

function errorMessage(error: unknown) {
  return error instanceof Error
    ? error.message
    : "The community request could not be completed.";
}

export function CommunityChat({
  slug,
  canPost,
  groupName,
}: {
  slug: string;
  canPost: boolean;
  groupName?: string;
}) {
  const { user } = useAuth();
  const client = useQueryClient();
  const [search, setSearch] = useState("");
  const query = useQuery({
    queryKey: ["community-messages", slug, search],
    queryFn: async () => (await communityService.messages(slug, search)).data,
    refetchInterval: isDjangoBackend ? 10_000 : false,
  });
  const send = useMutation({
    mutationFn: (body: string) => communityService.sendMessage(slug, body),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["community-messages", slug] });
    },
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const body = String(new FormData(form).get("body") || "").trim();
    if (!body) return;
    send.mutate(body, { onSuccess: () => form.reset() });
  }

  return (
    <section className="community-chat">
      <header>
        <div>
          <h2>{groupName ? `${groupName} chat` : "Community conversation"}</h2>
          <p>Visible only to active members and assigned leaders.</p>
        </div>
        <label className="community-chat__search">
          <Search />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search messages"
          />
        </label>
      </header>
      <div className="community-chat__messages" aria-live="polite">
        {query.isPending ? (
          <LoadingState label="Loading messages" />
        ) : query.isError ? (
          <ErrorState
            description={errorMessage(query.error)}
            onRetry={() => void query.refetch()}
          />
        ) : query.data.length ? (
          query.data.map((message: CommunityMessage) => (
            <article
              className={
                message.sender_id === user?.id
                  ? "community-message community-message--own"
                  : "community-message"
              }
              key={message.id}
            >
              <span>
                {message.sender_name
                  .split(/\s+/)
                  .slice(0, 2)
                  .map((part) => part[0])
                  .join("")}
              </span>
              <div>
                <header>
                  <strong>{message.sender_name}</strong>
                  <time>
                    {new Date(message.created_at).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </time>
                </header>
                <p>{message.body}</p>
              </div>
            </article>
          ))
        ) : (
          <EmptyState
            icon={<MessageSquareText />}
            title="The conversation is ready"
            description="The first community message will appear here."
          />
        )}
      </div>
      {canPost ? (
        <form className="community-chat__composer" onSubmit={submit}>
          <label>
            <span className="sr-only">Message</span>
            <textarea
              name="body"
              maxLength={4000}
              placeholder="Write a message to the community"
              required
            />
          </label>
          <Button type="submit" icon={<Send />} loading={send.isPending}>
            Send
          </Button>
          {send.isError && (
            <div className="form-error" role="alert">
              {errorMessage(send.error)}
            </div>
          )}
        </form>
      ) : (
        <div className="community-chat__locked">
          <ShieldCheck /> This community is currently leader-broadcast only.
        </div>
      )}
    </section>
  );
}
