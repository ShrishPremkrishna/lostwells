"use client";

import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { MapboxOverlay } from "@deck.gl/mapbox";
import { ScatterplotLayer } from "@deck.gl/layers";
import type { CandidateLite, DocumentedWells } from "@/lib/types";
import { scoreRGB, TEAL, DANGER } from "@/lib/colors";

// Free, no-token dark basemap (renders in the user's browser).
const STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

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
      style: STYLE,
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
          getFillColor: [TEAL[0], TEAL[1], TEAL[2], 26],
          radiusUnits: "pixels",
          getRadius: 1.3,
          radiusMinPixels: 0.4,
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
        getFillColor: (d) => {
          const [r, g, b] = scoreRGB(d.score.composite);
          return [r, g, b, d.well_id === selectedId ? 255 : 200];
        },
        getRadius: (d) => 4 + d.score.composite / 11,
        radiusUnits: "pixels",
        radiusMinPixels: 2.5,
        radiusMaxPixels: 22,
        stroked: true,
        getLineColor: (d) => (d.well_id === selectedId ? [255, 255, 255, 255] : [0, 0, 0, 90]),
        getLineWidth: (d) => (d.well_id === selectedId ? 2 : 0.5),
        lineWidthUnits: "pixels",
        pickable: true,
        autoHighlight: true,
        highlightColor: [255, 255, 255, 60],
        onClick: (info) => info.object && onSelect((info.object as CandidateLite).well_id),
        onHover: (info) =>
          onHover((info.object as CandidateLite) ?? null, info.x ?? 0, info.y ?? 0),
        updateTriggers: { getFillColor: selectedId, getLineColor: selectedId, getLineWidth: selectedId },
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

  return <div ref={containerRef} className="absolute inset-0" />;
}
