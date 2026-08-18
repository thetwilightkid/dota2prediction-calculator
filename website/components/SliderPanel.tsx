"use client";

import styles from "./SliderPanel.module.css";
import { useWeights } from "@/lib/WeightsContext";
import type { RatingWeights } from "@/lib/rating";

const SLIDERS: { key: keyof RatingWeights; label: string; hint: string }[] = [
  { key: "elo", label: "Datdota rating", hint: "Their Glicko-2 rating from datdota, an independent rating service that tracks pro matches worldwide" },
  { key: "formPretournament", label: "Pre-International form", hint: "How often they were winning before TI2026 started, weighted by how big those tournaments were" },
  { key: "formGroupStage", label: "Group Stage form", hint: "How often they won during TI2026's real Group Stage specifically - the freshest, most relevant signal" },
  { key: "market", label: "Liquipedia / EPT / ESL ranking", hint: "Average pre-tournament ranking from Liquipedia, the Esports Power Tier list, and ESL's regional rankings" },
  { key: "stability", label: "Comeback ability", hint: "How often they win after falling behind, minus how often they lose after being ahead - off by default" },
  { key: "patchImpact", label: "Latest patch effect", hint: "Whether the newest balance update helps or hurts the heroes they like to play - off by default" },
];

export default function SliderPanel() {
  const { weights, setWeights, saveWeights, resetWeights, isDefault, hasSavedPreset } = useWeights();

  function setWeight(key: keyof RatingWeights, value: number) {
    setWeights({ ...weights, [key]: value });
  }

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h2>Adjust what matters most</h2>
      </div>
      <p className={styles.subtitle}>
        Drag the sliders to see how focusing on different factors changes the team rankings and predicted results,
        right here in your browser.
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
      <div className={styles.actions}>
        <button className={styles.saveBtn} onClick={saveWeights}>
          Save my settings
        </button>
        <button className={styles.resetBtn} onClick={resetWeights} disabled={isDefault}>
          Reset to default
        </button>
      </div>
      {hasSavedPreset && <p className={styles.savedNote}>Saved settings will load automatically next time you visit.</p>}
    </div>
  );
}
