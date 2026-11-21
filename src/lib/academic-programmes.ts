// Chrisland University undergraduate catalogue, grouped by current college/faculty.
// Sources: official college pages and Academic Planning programme list (2026).
export const ACADEMIC_PROGRAMMES = [
  {
    college: "Arts, Management and Social Sciences",
    programmes: [
      "Accounting",
      "Banking and Finance",
      "Business Administration",
      "Criminology and Security Studies",
      "Economics",
      "English",
      "International Relations and Diplomacy",
      "Mass Communication",
      "Political Science",
      "Psychology",
    ],
  },
  {
    college: "Natural and Applied Sciences",
    programmes: [
      "Biochemistry",
      "Computer Science",
      "Cybersecurity",
      "Industrial Chemistry",
      "Mathematics",
      "Microbiology",
      "Molecular Biology and Biotechnology",
      "Software Engineering",
    ],
  },
  {
    college: "Basic Medical Sciences",
    programmes: ["Medical Laboratory Science", "Physiotherapy", "Public Health"],
  },
  { college: "Nursing Sciences", programmes: ["Nursing Science"] },
  { college: "Law", programmes: ["Law"] },
  { college: "Foundation", programmes: ["JUPEB"] },
] as const;
