"use client";

import { useCallback, useEffect, useState } from "react";

// Starred niches, kept per-browser in localStorage. No backend needed for a personal
// bookmark; a shared/DB-backed version can replace this later without changing callers.
const STORAGE_KEY = "omni_starred_niches";

function read(): number[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as number[]) : [];
  } catch {
    return [];
  }
}

export function useStars() {
  const [starredIds, setStarredIds] = useState<number[]>([]);

  useEffect(() => {
    setStarredIds(read());
  }, []);

  const isStarred = useCallback((id: number) => starredIds.includes(id), [starredIds]);

  const toggle = useCallback((id: number) => {
    setStarredIds((prev) => {
      const next = prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id];
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      } catch {
        // Private mode / blocked storage — the star still toggles for this session.
      }
      return next;
    });
  }, []);

  return { starredIds, isStarred, toggle };
}
