"use client";

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { DEFAULT_WEIGHTS, type RatingWeights } from "./rating";

const STORAGE_KEY = "ti2026-weights-preset-v1";

interface WeightsContextValue {
  weights: RatingWeights;
  setWeights: (w: RatingWeights) => void;
  saveWeights: () => void;
  resetWeights: () => void;
  hasSavedPreset: boolean;
  isDefault: boolean;
}

const WeightsContext = createContext<WeightsContextValue | null>(null);

function loadSaved(): RatingWeights | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    const keys: (keyof RatingWeights)[] = ["elo", "form", "market", "stability", "patchImpact"];
    if (keys.every((k) => typeof parsed[k] === "number")) return parsed as RatingWeights;
    return null;
  } catch {
    return null;
  }
}

export function WeightsProvider({ children }: { children: ReactNode }) {
  // Starts at defaults on the server and on first client render (to match SSR
  // output), then swaps in any saved preset right after mount.
  const [weights, setWeightsState] = useState<RatingWeights>(DEFAULT_WEIGHTS);
  const [hasSavedPreset, setHasSavedPreset] = useState(false);

  useEffect(() => {
    // setState deferred into a callback (not called directly in the effect
    // body) per react-hooks/set-state-in-effect.
    const handle = setTimeout(() => {
      const saved = loadSaved();
      if (saved) {
        setWeightsState(saved);
        setHasSavedPreset(true);
      }
    }, 0);
    return () => clearTimeout(handle);
  }, []);

  function setWeights(w: RatingWeights) {
    setWeightsState(w);
  }

  function saveWeights() {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(weights));
    setHasSavedPreset(true);
  }

  function resetWeights() {
    setWeightsState(DEFAULT_WEIGHTS);
  }

  const isDefault = useMemo(
    () => (Object.keys(weights) as (keyof RatingWeights)[]).every((k) => weights[k] === DEFAULT_WEIGHTS[k]),
    [weights]
  );

  const value: WeightsContextValue = { weights, setWeights, saveWeights, resetWeights, hasSavedPreset, isDefault };

  return <WeightsContext.Provider value={value}>{children}</WeightsContext.Provider>;
}

export function useWeights(): WeightsContextValue {
  const ctx = useContext(WeightsContext);
  if (!ctx) throw new Error("useWeights must be used within a WeightsProvider");
  return ctx;
}
