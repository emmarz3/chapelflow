export const BRAND_ASSETS = {
  chapelMark: "/chapelflow-mark.svg",
  chapelFlowBrand: "/chapelflow-brand.jpg",
  institutionLogo: "/chrisland-university-chapel.png",
} as const;

export const BRAND_FALLBACKS: Record<string, string> = {
  [BRAND_ASSETS.chapelFlowBrand]: BRAND_ASSETS.chapelMark,
  [BRAND_ASSETS.institutionLogo]: BRAND_ASSETS.chapelMark,
};

export function brandFallbackFor(src: string) {
  return BRAND_FALLBACKS[src] || BRAND_ASSETS.chapelMark;
}
