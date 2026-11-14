export interface ChapelProgramme {
  id: string;
  title: string;
  date: string | null;
  venue: string;
  detail?: string;
  displayDate?: string;
  sortDate?: string;
}

export const CHAPEL_PROGRAMMES: ChapelProgramme[] = [
  { id: "retreat-2026-11-13", title: "Chapel Workers Retreat 2026", date: "2026-11-13", venue: "University Auditorium", detail: "Friday retreat session" },
  { id: "retreat-2026-11-14", title: "Chapel Workers Retreat 2026", date: "2026-11-14", venue: "University Auditorium", detail: "Saturday retreat session" },
  { id: "commanding-excellence-2026-11-15", title: "3 Sundays of Commanding Excellence", date: "2026-11-15", venue: "University Worship Centre", detail: "8:00 AM (1st service) and 10:30 AM (2nd service) · Raising Godly Morals & Instilling Spiritual Virtues" },
  { id: "commanding-excellence-2026-11-22", title: "3 Sundays of Commanding Excellence", date: "2026-11-22", venue: "University Worship Centre", detail: "8:00 AM (1st service) and 10:30 AM (2nd service) · Raising Godly Morals & Instilling Spiritual Virtues" },
  { id: "commanding-excellence-2026-11-29", title: "3 Sundays of Commanding Excellence", date: "2026-11-29", venue: "University Worship Centre", detail: "8:00 AM (1st service) and 10:30 AM (2nd service) · Raising Godly Morals & Instilling Spiritual Virtues" },
  { id: "book-reading-2026-12-06", title: "Book Reading Sunday", date: "2026-12-06", venue: "Venue to be announced" },
  { id: "revival-2026-12-13", title: "End of the Year Revival and Anointing Service", date: "2026-12-13", venue: "Venue to be announced" },
  { id: "christmas-carol-2026-12-17", title: "Christmas Carol & EOY Thanksgiving", date: "2026-12-17", venue: "Venue to be announced" },
  { id: "departmental-harvest-2027-02-21", title: "Departmental Harvest", date: "2027-02-21", venue: "Venue to be announced" },
  { id: "business-sunday-2027-02-28", title: "Business Sunday", date: "2027-02-28", venue: "Venue to be announced" },
  { id: "all-white-baptism-2027-03-07", title: "All White Service & Baptism", date: "2027-03-07", venue: "Venue to be announced" },
  { id: "march-thanksgiving-2027", title: "March Thanksgiving", date: null, displayDate: "March 2027 · exact date to be announced", sortDate: "2027-03-01", venue: "Venue to be announced" },
];
