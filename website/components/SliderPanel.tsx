"use client";

import styles from "./SliderPanel.module.css";
import { DEFAULT_WEIGHTS, type RatingWeights } from "@/lib/rating";

interface SliderPanelProps {
  weights: RatingWeights;
  onChange: (weights: RatingWeights) => void;
}

const SLIDERS: { key: keyof RatingWeights; label: string; hint: string }[] = [
  { key: "elo", label: "ELO (datdota Glicko-2)", hint: "External market rating consensus signal" },
  { key: "form", label: "Current form", hint: "Our own decayed, tier-weighted win rate" },
  { key: "market", label: "Market consensus", hint: "EPT / ESL / Liquipedia rating agreement" },
  { key: "stability", label: "Stability (resilience)", hint: "Comeback rate minus choke rate - off by default" },
  { key: "patchImpact", label: "Patch 7.41e impact", hint: "Live winrate-trend of each team's pick pool - off by default" },
];

export default function SliderPanel({ weights, onChange }: SliderPanelProps) {
  function setWeight(key: keyof RatingWeights, value: number) {
    onChange({ ...weights, [key]: value });
  }

  const isDefault = SLIDERS.every((s) => weights[s.key] === DEFAULT_WEIGHTS[s.key]);

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h2>Criteria weighting</h2>
        <button className={styles.resetBtn} onClick={() => onChange(DEFAULT_WEIGHTS)} disabled={isDefault}>
          Reset to default
        </button>
      </div>
      <p className={styles.subtitle}>
        Drag to see how re-weighting each signal reorders the teams and shifts placement odds, computed live in your
        browser from the same components stored in team_composite_ratings.json.
      </p>
      <div className={styles.sliders}>
        {SLIDERS.map((s) => (
          <div key={s.key} className={styles.sliderRow}>
            <div className={styles.sliderLabelRow}>
              <label htmlFor={`slider-${s.key}`}>{s.label}</label>
              <span className={styles.value}>{weights[s.key].toFixed(2)}</span>
            </div>
            <input
              id={`slider-${s.key}`}
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={weights[s.key]}
              onChange={(e) => setWeight(s.key, Number(e.target.value))}
              className={styles.range}
            />
            <div className={styles.hint}>{s.hint}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
