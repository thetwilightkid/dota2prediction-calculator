// Team logo assets, copied into public/teams/ from the user's sibling
// dota2fantasy-calculator project (same 16 TI2026 orgs, same artwork). Static
// site assets rather than pipeline output, so they live here instead of being
// baked by scripts/build-dataset.js.
//
// Mixed extensions are intentional and match the source project: 12 orgs have
// a compact .webp crest, the other 4 only exist as .svg there.
export const TEAM_LOGO: Record<number, string> = {
  9572001: "/teams/vision.webp", // Team Vision
  9247354: "/teams/falcons.webp", // Team Falcons
  8255888: "/teams/boomboys.svg", // BoomBoys
  10150413: "/teams/iron-wing.webp", // Iron Wing
  10136357: "/teams/nigma.webp", // Nigma Galaxy
  2586976: "/teams/og.webp", // OG
  10150538: "/teams/lgd.webp", // LGD Gaming
  5017210: "/teams/team-resilience.svg", // Team Resilience
  9823272: "/teams/yandex.webp", // Team Yandex
  2163: "/teams/liquid.webp", // Team Liquid
  9467224: "/teams/aurora.webp", // Aurora Gaming
  7119388: "/teams/spirit.webp", // Team Spirit
  8261500: "/teams/xtreme.webp", // Xtreme Gaming
  726228: "/teams/vici.svg", // Vici Gaming
  9964962: "/teams/gamerlegion.svg", // GamerLegion
  10149530: "/teams/huligani.webp", // HULIGANI
};

export function teamLogo(teamId: number): string | undefined {
  return TEAM_LOGO[teamId];
}
