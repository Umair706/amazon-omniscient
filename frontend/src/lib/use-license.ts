"use client";

import { useEffect, useState } from "react";

import api from "@/lib/api";

// Mirrors LicenseStatusResponse from backend/app/api/license.py.
export interface LicenseStatus {
  tier: string;
  features: string[];
  valid: boolean;
  reason: string;
  expires: string | null;
}

const FREE_TIER: LicenseStatus = {
  tier: "free",
  features: [],
  valid: false,
  reason: "",
  expires: null,
};

// Reads the installed license once so the UI can lock premium controls. A failed
// request degrades to the free tier — the backend is the real gate, this is display only.
export function useLicense() {
  const [license, setLicense] = useState<LicenseStatus>(FREE_TIER);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let active = true;
    api
      .get<LicenseStatus>("/api/v1/license")
      .then((res) => {
        if (active) setLicense(res.data);
      })
      .catch(() => {
        if (active) setLicense(FREE_TIER);
      })
      .finally(() => {
        if (active) setLoaded(true);
      });
    return () => {
      active = false;
    };
  }, []);

  const has = (feature: string) => license.features.includes(feature);
  return { license, loaded, has };
}
