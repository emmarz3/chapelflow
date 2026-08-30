import { createHash, randomUUID } from "node:crypto";
import type { Database } from "./db.js";
import { inTransaction } from "./db.js";

type CommunitySeed = {
  name: string;
  slug: string;
  type: "unit" | "campus_fellowship";
  leader: string;
  position?: string;
  assistant?: { name: string; position: string };
};

export const organizationCommunities: CommunitySeed[] = [
  {
    name: "Intercessory",
    slug: "intercessory",
    type: "unit",
    leader: "Destiny Awunudiogba",
  },
  {
    name: "Chapel Protocol",
    slug: "chapel-protocol",
    type: "unit",
    leader: "Abodunde Dayo",
  },
  {
    name: "Music",
    slug: "music",
    type: "unit",
    leader: "Olaoti Mofiyinfoluwa",
    position: "Head of Music",
    assistant: { name: "Agu Mary Irene", position: "Assistant Head of Music" },
  },
  {
    name: "Instrumentalists",
    slug: "instrumentalists",
    type: "unit",
    leader: "George Edafe",
    position: "Head of Instrumentalists",
  },
  {
    name: "Ushering",
    slug: "ushering",
    type: "unit",
    leader: "Munachiso Okeke",
    position: "Chief Usher",
    assistant: { name: "Samuel Obehioye", position: "Assistant Chief Usher" },
  },
  {
    name: "Sanctuary Keepers",
    slug: "sanctuary-keepers",
    type: "unit",
    leader: "Iwalola Egbeyemi",
    position: "Head of Sanctuary Keepers",
    assistant: {
      name: "Ayobami Ogunrinde",
      position: "Assistant Head of Sanctuary Keepers",
    },
  },
  {
    name: "Media & ICT",
    slug: "media-ict",
    type: "unit",
    leader: "Oluwayinka Godslove",
  },
  {
    name: "Social Media",
    slug: "social-media",
    type: "unit",
    leader: "Adebayo Ifeoluwa",
  },
  { name: "Library", slug: "library", type: "unit", leader: "Ajiboye Isaac" },
  {
    name: "Drama Team",
    slug: "drama-team",
    type: "unit",
    leader: "Okoli Chinemerem Uzuego",
  },
  {
    name: "Technical & Sound",
    slug: "technical-sound",
    type: "unit",
    leader: "Akintunde Tundun",
  },
  {
    name: "Love Campus Fellowship",
    slug: "love-campus-fellowship",
    type: "campus_fellowship",
    leader: "Dada Mofopefoluwa",
  },
  {
    name: "Truth Campus Fellowship",
    slug: "truth-campus-fellowship",
    type: "campus_fellowship",
    leader: "Fayemi Ajibola",
  },
  {
    name: "Favour Campus Fellowship",
    slug: "favour-campus-fellowship",
    type: "campus_fellowship",
    leader: "Ojekunle Daniel",
  },
  {
    name: "Integrity Campus Fellowship",
    slug: "integrity-campus-fellowship",
    type: "campus_fellowship",
    leader: "Balogun Temitope",
  },
  {
    name: "Righteousness Campus Fellowship",
    slug: "righteousness-campus-fellowship",
    type: "campus_fellowship",
    leader: "Adebayo Sharon",
  },
  {
    name: "Mercy Campus Fellowship",
    slug: "mercy-campus-fellowship",
    type: "campus_fellowship",
    leader: "Aborisade Darasimi",
  },
  {
    name: "Excellence Campus Fellowship",
    slug: "excellence-campus-fellowship",
    type: "campus_fellowship",
    leader: "Adewale Phillip",
  },
  {
    name: "Grace Campus Fellowship",
    slug: "grace-campus-fellowship",
    type: "campus_fellowship",
    leader: "Oyenekan Oluwanifemi",
  },
  {
    name: "Outstanding Campus Fellowship",
    slug: "outstanding-campus-fellowship",
    type: "campus_fellowship",
    leader: "Divine Awunudiogba",
  },
  {
    name: "Peace Campus Fellowship",
    slug: "peace-campus-fellowship",
    type: "campus_fellowship",
    leader: "Adebesin Kofoworola",
  },
];

const globalPositions = [
  ["Student Chaplain", "Akintobi Oluwabori Favour"],
  ["Treasurer", "Olutanwa Esther"],
  ["Male Hostel Fellowship Coordinator", "Christopher Olanrewaju"],
  ["Female Hostel Fellowship Coordinator 1", "Elizabeth Ajayi"],
  ["Female Hostel Fellowship Coordinator 2", null],
  ["Assistant Student Chaplain — VLBC Annex Hostel", "Aderonmu Adeola"],
] as const;

function stableUuid(key: string) {
  const hex = createHash("sha256")
    .update(`chapelflow:${key}`)
    .digest("hex")
    .slice(0, 32);
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-4${hex.slice(13, 16)}-a${hex.slice(17, 20)}-${hex.slice(20)}`;
}

export async function seedOrganization(database: Database) {
  await inTransaction(database, async (client) => {
    for (const community of organizationCommunities) {
      const communityId = stableUuid(`community:${community.slug}`);
      await client.query(
        `INSERT INTO communities (id, name, slug, type, description)
         VALUES ($1, $2, $3, $4, $5)
         ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name, type = EXCLUDED.type`,
        [
          communityId,
          community.name,
          community.slug,
          community.type,
          `${community.name} private ChapelFlow workspace.`,
        ],
      );
      await client.query(
        `INSERT INTO conversations (id, community_id, type)
         VALUES ($1, $2, 'community') ON CONFLICT (community_id, type) DO NOTHING`,
        [stableUuid(`conversation:${community.slug}`), communityId],
      );
      const assignments = [
        {
          name: community.leader,
          position:
            community.position ??
            (community.type === "unit" ? "Unit Leader" : "Fellowship Leader"),
        },
        ...(community.assistant ? [community.assistant] : []),
      ];
      for (const assignment of assignments) {
        const positionId = stableUuid(
          `position:community:${assignment.position}`,
        );
        await client.query(
          `INSERT INTO leadership_positions (id, name, scope_type, capabilities)
           VALUES ($1, $2, 'community', $3::jsonb)
           ON CONFLICT (name, scope_type) DO NOTHING`,
          [
            positionId,
            assignment.position,
            JSON.stringify(["announce", "event", "moderate", "members"]),
          ],
        );
        const existing = await client.query(
          `SELECT 1 FROM leadership_assignments
            WHERE position_id = $1 AND community_id = $2 AND active = TRUE`,
          [positionId, communityId],
        );
        if (!existing.rows.length) {
          await client.query(
            `INSERT INTO leadership_assignments
              (id, position_id, assignee_name, community_id, active)
             VALUES ($1, $2, $3, $4, TRUE)`,
            [randomUUID(), positionId, assignment.name, communityId],
          );
        }
      }
    }

    for (const [positionName, assigneeName] of globalPositions) {
      const positionId = stableUuid(`position:global:${positionName}`);
      await client.query(
        `INSERT INTO leadership_positions (id, name, scope_type, capabilities)
         VALUES ($1, $2, 'global', '[]'::jsonb)
         ON CONFLICT (name, scope_type) DO NOTHING`,
        [positionId, positionName],
      );
      if (assigneeName) {
        const existing = await client.query(
          `SELECT 1 FROM leadership_assignments
            WHERE position_id = $1 AND community_id IS NULL AND active = TRUE`,
          [positionId],
        );
        if (!existing.rows.length) {
          await client.query(
            `INSERT INTO leadership_assignments
              (id, position_id, assignee_name, community_id, active)
             VALUES ($1, $2, $3, NULL, TRUE)`,
            [randomUUID(), positionId, assigneeName],
          );
        }
      }
    }
  });
}
