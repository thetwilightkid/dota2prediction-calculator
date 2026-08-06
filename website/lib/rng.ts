// Small seedable PRNG (mulberry32) + Box-Muller gaussian sampler, so the
// client-side Monte Carlo re-simulation is deterministic for a given seed
// (useful for reproducible "share this scenario" style links later) without
// depending on any external library.
export class Rng {
  private state: number;
  private cachedGaussian: number | null = null;

  constructor(seed: number) {
    this.state = seed >>> 0;
  }

  // Uniform float in [0, 1)
  random(): number {
    this.state |= 0;
    this.state = (this.state + 0x6d2b79f5) | 0;
    let t = Math.imul(this.state ^ (this.state >>> 15), 1 | this.state);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  }

  // Uniform integer in [0, n)
  randInt(n: number): number {
    return Math.floor(this.random() * n);
  }

  // Normal(mean, sigma) via Box-Muller, caching the second sample per pair of draws.
  gauss(mean: number, sigma: number): number {
    if (this.cachedGaussian !== null) {
      const z = this.cachedGaussian;
      this.cachedGaussian = null;
      return mean + sigma * z;
    }
    let u1 = this.random();
    if (u1 < 1e-12) u1 = 1e-12;
    const u2 = this.random();
    const r = Math.sqrt(-2 * Math.log(u1));
    const z0 = r * Math.cos(2 * Math.PI * u2);
    const z1 = r * Math.sin(2 * Math.PI * u2);
    this.cachedGaussian = z1;
    return mean + sigma * z0;
  }
}
