"use client";

import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { MapboxOverlay } from "@deck.gl/mapbox";
import { ScatterplotLayer } from "@deck.gl/layers";
import type { CandidateLite, DocumentedWells } from "@/lib/types";
import { TEAL, EMBER, DANGER } from "@/lib/colors";

// Free, no-token basemaps. TOPO = Carto Voyager (light topographic, matches the
// uidesign.md theme); SATELLITE/HYBRID = ESRI World Imagery rasters (no token).
const STYLE_TOPO = "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json";
const ESRI_IMAGERY =
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";
const ESRI_REF =
  "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}";

type Basemap = "topo" | "satellite" | "hybrid";

function styleFor(b: Basemap): string | maplibregl.StyleSpecification {
  if (b === "topo") return STYLE_TOPO;
  const layers: maplibregl.LayerSpecification[] = [
    { id: "sat", type: "raster", source: "sat" } as maplibregl.LayerSpecification,
  ];
  const sources: Record<string, maplibregl.SourceSpecification> = {
    sat: { type: "raster", tiles: [ESRI_IMAGERY], tileSize: 256, attribution: "Esri, Maxar" },
  };
  if (b === "hybrid") {
    sources.ref = { type: "raster", tiles: [ESRI_REF], tileSize: 256 };
    layers.push({ id: "ref", type: "raster", source: "ref" } as maplibregl.LayerSpecification);
  }
  return { version: 8, sources, layers } as maplibregl.StyleSpecification;
}

export interface FocusTarget {
  lon: number;
  lat: number;
  zoom?: number;
  nonce: number;
}

interface Props {
  documented: DocumentedWells | null;
  candidates: CandidateLite[];
  heroes: CandidateLite[];
  selectedId: string | null;
  showDocumented: boolean;
  focus: FocusTarget | null;
  fitNonce: number;
  onSelect: (id: string) => void;
  onHover: (c: CandidateLite | null, x: number, y: number) => void;
}

export default function MapView(props: Props) {
  const { documented, candidates, heroes, selectedId, showDocumented, focus, fitNonce, onSelect, onHover } = props;
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const overlayRef = useRef<MapboxOverlay | null>(null);
  const positionsRef = useRef<Float32Array | null>(null);
  const [basemap, setBasemap] = useState<Basemap>("topo");

  // Swap the basemap on toggle. The deck overlay is a separate control/canvas,
  // so it survives setStyle and keeps its layers.
  useEffect(() => {
    if (mapRef.current) mapRef.current.setStyle(styleFor(basemap));
  }, [basemap]);

  // declarative camera control (avoids ref-forwarding through next/dynamic)
  useEffect(() => {
    if (focus && mapRef.current) {
      mapRef.current.flyTo({
        center: [focus.lon, focus.lat],
        zoom: focus.zoom ?? 13.5,
        speed: 1.1,
        curve: 1.5,
        essential: true,
      });
    }
  }, [focus?.nonce]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (fitNonce > 0 && mapRef.current) {
      mapRef.current.flyTo({ center: [-95, 38], zoom: 3.8, speed: 1.0 });
    }
  }, [fitNonce]);

  // init map once
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: STYLE_TOPO,
      center: [-95, 38],
      zoom: 3.7,
      attributionControl: false,
      maxZoom: 18,
      dragRotate: false,
    });
    map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");
    const overlay = new MapboxOverlay({ interleaved: false, layers: [] });
    map.addControl(overlay as unknown as maplibregl.IControl);
    mapRef.current = map;
    overlayRef.current = overlay;
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // build the documented backbone binary positions once
  useEffect(() => {
    if (!documented) return;
    const n = documented.count;
    const pos = new Float32Array(n * 2);
    for (let i = 0; i < n; i++) {
      pos[i * 2] = documented.lon[i];
      pos[i * 2 + 1] = documented.lat[i];
    }
    positionsRef.current = pos;
  }, [documented]);

  // re-render deck layers on data/selection change
  useEffect(() => {
    const overlay = overlayRef.current;
    if (!overlay) return;
    const layers: ScatterplotLayer[] = [];

    if (documented && positionsRef.current && showDocumented) {
      layers.push(
        new ScatterplotLayer({
          id: "documented",
          data: {
            length: documented.count,
            attributes: { getPosition: { value: positionsRef.current, size: 2 } },
          },
          getFillColor: [TEAL[0], TEAL[1], TEAL[2], 90],
          radiusUnits: "pixels",
          getRadius: 1.3,
          radiusMinPixels: 0.5,
          radiusMaxPixels: 2.6,
          pickable: false,
          parameters: { depthTest: false },
        })
      );
    }

    layers.push(
      new ScatterplotLayer<CandidateLite>({
        id: "candidates",
        data: candidates,
        getPosition: (d) => [d.lon, d.lat],
        // Discovered wells: one color, sized in METERS so they grow with zoom —
        // near the documented-overlay size when the whole US is in view, growing
        // to a comfortably clickable target when zoomed in (floored/capped in px).
        // Impact score lives in the list/dossier, not the map marker. Selection
        // bumps size + adds a white stroke.
        getFillColor: (d) =>
          d.well_id === selectedId
            ? [13, 13, 13, 255] // ink — stands out on the light map + green cloud
            : [EMBER[0], EMBER[1], EMBER[2], 205],
        getRadius: (d) => (d.well_id === selectedId ? 150 : 55),
        radiusUnits: "meters",
        radiusMinPixels: 1.8,
        radiusMaxPixels: 13,
        stroked: true,
        getLineColor: (d) => (d.well_id === selectedId ? [255, 255, 255, 255] : [255, 255, 255, 70]),
        getLineWidth: (d) => (d.well_id === selectedId ? 2.5 : 0.3),
        lineWidthUnits: "pixels",
        pickable: true,
        autoHighlight: true,
        highlightColor: [255, 255, 255, 120],
        onClick: (info) => info.object && onSelect((info.object as CandidateLite).well_id),
        onHover: (info) =>
          onHover((info.object as CandidateLite) ?? null, info.x ?? 0, info.y ?? 0),
        updateTriggers: {
          getFillColor: selectedId,
          getRadius: selectedId,
          getLineColor: selectedId,
          getLineWidth: selectedId,
        },
      })
    );

    if (heroes.length) {
      layers.push(
        new ScatterplotLayer<CandidateLite>({
          id: "heroes",
          data: heroes,
          getPosition: (d) => [d.lon, d.lat],
          getFillColor: [DANGER[0], DANGER[1], DANGER[2], 235],
          getRadius: 9,
          radiusUnits: "pixels",
          radiusMinPixels: 6,
          radiusMaxPixels: 26,
          stroked: true,
          getLineColor: [255, 240, 235, 255],
          getLineWidth: 2,
          lineWidthUnits: "pixels",
          pickable: true,
          onClick: (info) => info.object && onSelect((info.object as CandidateLite).well_id),
          onHover: (info) =>
            onHover((info.object as CandidateLite) ?? null, info.x ?? 0, info.y ?? 0),
        })
      );
    }

    overlay.setProps({ layers });
  }, [documented, candidates, heroes, selectedId, showDocumented, onSelect, onHover]);

  // Inline position/inset: MapLibre's stylesheet sets `.maplibregl-map{position:
  // relative}` and loads after Tailwind, overriding the `absolute` utility — which
  // collapses the container to 0px height (black map). Inline styles win.
  return (
    <>
      <div
        ref={containerRef}
        className="absolute inset-0"
        style={{ position: "absolute", top: 0, right: 0, bottom: 0, left: 0 }}
      />
      {/* Map style toggle — bottom center, dark "field notes on glass" pill. */}
      <div
        className="absolute bottom-6 left-1/2 z-20 flex -translate-x-1/2 overflow-hidden"
        style={{ background: "rgba(13,13,13,0.9)", border: "1px solid rgba(255,255,255,0.12)" }}
      >
        {(["topo", "satellite", "hybrid"] as Basemap[]).map((b) => (
          <button
            key={b}
            onClick={() => setBasemap(b)}
            className="px-3.5 py-1.5 text-[11px] uppercase tracking-[0.08em] transition-colors"
            style={{
              color: basemap === b ? "#fff" : "rgba(255,255,255,0.55)",
              background: basemap === b ? "var(--color-accent)" : "transparent",
            }}
          >
            {b}
          </button>
        ))}
      </div>
    </>
  );
}
