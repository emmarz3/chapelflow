import {
  BookOpen,
  Camera,
  DoorOpen,
  Flame,
  Heart,
  Megaphone,
  Mic,
  Music,
  ShieldCheck,
  Smile,
  Star,
  Users,
  type LucideIcon,
} from "lucide-react";
import type { UnitIcon } from "../../lib/homepage-content";

export const UNIT_ICON_COMPONENTS: Record<UnitIcon, LucideIcon> = {
  music: Music,
  door: DoorOpen,
  camera: Camera,
  flame: Flame,
  smile: Smile,
  shield: ShieldCheck,
  heart: Heart,
  book: BookOpen,
  users: Users,
  mic: Mic,
  megaphone: Megaphone,
  star: Star,
};

export const UNIT_ICON_LABELS: Record<UnitIcon, string> = {
  music: "Music note",
  door: "Door (welcome)",
  camera: "Camera",
  flame: "Flame (prayer)",
  smile: "Smile (drama)",
  shield: "Shield (protocol)",
  heart: "Heart (care)",
  book: "Book (study)",
  users: "People",
  mic: "Microphone",
  megaphone: "Megaphone",
  star: "Star",
};
