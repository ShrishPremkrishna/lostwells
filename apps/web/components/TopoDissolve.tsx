"use client";

import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { Candidate } from "@/lib/types";

// Free, no-token raster basemaps (render in the user's browser):
//  - "before": ESRI USA Topo Maps = scanned historical USGS topographic quads.
//  - "after" : ESRI World Imagery = present-day satellite.
const TOPO = "https://services.arcgisonline.com/ArcGIS/rest/services/USA_Topo_Maps/MapServer/tile/{z}/{y}/{x}";
const SAT = "https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";

function rasterStyle(tiles: string, attribution: string) {
  return {
    version: 8 as const,
    sources: { r: { type: "raster" as const, tiles: [tiles], tileSize: 256, attribution } },
    layers: [{ id: "r", type: "raster" as const, source: "r" }],
  };
}

export function TopoDissolve({ hero, onClose }: { hero: Candidate; onClose: () => void }) {
  const beforeRef = useRef<HTMLDivElement>(null);
  const afterRef = useRef<HTMLDivElement>(null);
  const [clip, setClip] = useState(62); // % of width showing the topo (left)
  const draggingRef = useRef(false);

  useEffect(() => {
    let beforeMap: any, afterMap: any, cancelled = false;
    (async () => {
      const maplibregl = (await import("maplibre-gl")).default;
      // maplibre-gl CSS is imported globally by MapView.
      if (cancelled || !beforeRef.current || !afterRef.current) return;
      const center: [number, number] = [hero.lon, hero.lat];
      const opts = { center, zoom: 15.5, attributionControl: false as const, dragRotate: false };
      beforeMap = new maplibregl.Map({
        container: beforeRef.current, style: rasterStyle(TOPO, "USGS / Esri") as any,
        interactive: false, ...opts,
      });
      afterMap = new maplibregl.Map({
        container: afterRef.current, style: rasterStyle(SAT, "Esri World Imagery") as any,
        ...opts,
      });
      afterMap.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");
      // sync the non-interactive topo map to the satellite map's camera
      const sync = () => beforeMap.jumpTo({
        center: afterMap.getCenter(), zoom: afterMap.getZoom(),
        bearing: afterMap.getBearing(), pitch: afterMap.getPitch(),
      });
      afterMap.on("move", sync);
      // cinematic auto-sweep on open
      afterMap.once("load", () => {
        let t = 0;
        const id = setInterval(() => {
          t += 0.04;
          const v = 62 + Math.sin(t) * 26;
          setClip(v);
          if (t > Math.PI) { clearInterval(id); setClip(58); }
        }, 40);
      });
    })();
    return () => { cancelled = true; beforeMap?.remove?.(); afterMap?.remove?.(); };
  }, [hero]);

  function onPointer(e: React.PointerEvent) {
    if (!draggingRef.current) return;
    const rect = (e.currentTarget as HTMLDivElement).getBoundingClientRect();
    const pct = ((e.clientX - rect.left) / rect.width) * 100;
    setClip(Math.max(4, Math.min(96, pct)));
  }

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        className="absolute inset-0 z-50 flex items-center justify-center bg-ink-950/90 p-6 backdrop-blur"
      >
        <motion.div
          initial={{ scale: 0.96, y: 16 }} animate={{ scale: 1, y: 0 }}
          className="relative h-[78vh] w-full max-w-5xl overflow-hidden rounded-2xl border border-white/10 shadow-panel"
          onPointerMove={onPointer}
          onPointerUp={() => (draggingRef.current = false)}
          onPointerLeave={() => (draggingRef.current = false)}
        >
          {/* satellite (after) underneath, full */}
          <div ref={afterRef} className="absolute inset-0" />
          {/* topo (before) on top, clipped from the right */}
          <div
            ref={beforeRef}
            className="absolute inset-0"
            style={{ clipPath: `inset(0 ${100 - clip}% 0 0)` }}
          />
          {/* swipe handle */}
          <div className="absolute inset-y-0 z-20" style={{ left: `${clip}%` }}>
            <div className="absolute inset-y-0 -ml-px w-0.5 bg-white/80" />
            <button
              onPointerDown={() => (draggingRef.current = true)}
              className="absolute top-1/2 -ml-4 -mt-4 flex h-8 w-8 cursor-ew-resize items-center justify-center rounded-full border border-white/70 bg-ink-900/90 text-[11px] text-white shadow-panel"
            >
              ⇆
            </button>
          </div>
          {/* well marker pulsing at the site */}
          <div className="pointer-events-none absolute left-1/2 top-1/2 z-20 -translate-x-1/2 -translate-y-1/2">
            <span className="absolute -left-3 -top-3 h-6 w-6 animate-pulsering rounded-full bg-danger/60" />
            <span className="block h-3 w-3 rounded-full bg-danger ring-2 ring-white" />
          </div>
          {/* labels */}
          <div className="pointer-events-none absolute left-4 top-4 z-20 max-w-xs rounded-md bg-ink-950/70 px-2 py-1 text-paper">
            <div className="text-[11px] font-medium">
              {hero.hero?.topo?.label ?? "historical topo"}
            </div>
            <div className="mt-0.5 text-[10px] text-paper/70">
              Shown: ESRI USA_Topo scanned-quad mosaic — displayed vintage is
              best-available and may differ from the labeled edition.
            </div>
          </div>
          <div className="pointer-events-none absolute right-4 top-4 z-20 rounded-md bg-ink-950/70 px-2 py-1 text-[11px] font-medium text-paper">
            today — satellite
          </div>
          {/* caption + close */}
          <div className="absolute inset-x-0 bottom-0 z-20 bg-gradient-to-t from-ink-950/95 to-transparent p-5 pt-12">
            <div className="flex items-end justify-between gap-4">
              <div>
                <div className="text-[10px] font-semibold uppercase tracking-[0.18em]" style={{ color: "#7aae8a" }}>
                  Discovered candidate · {hero.hero?.pathway ?? "pathway"}
                </div>
                <h3 className="font-display mt-1 text-2xl text-paper">{hero.hero?.title}</h3>
                <p className="mt-0.5 text-xs text-ink-300">{hero.hero?.place}</p>
                <p className="mt-2 max-w-2xl text-[13px] leading-relaxed text-ink-200">
                  {hero.hero?.blurb}
                </p>
              </div>
              <button
                onClick={onClose}
                className="shrink-0 rounded-lg border border-white/20 bg-ink-900/80 px-3 py-1.5 text-[12px] text-ink-100 hover:bg-white/10"
              >
                Close
              </button>
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
