"use client";

import { useEffect } from "react";

export function ClientBootstrap() {
  useEffect(() => {
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch(() => {
        // Ignore SW register failures in development.
      });
    }
  }, []);
  return null;
}
