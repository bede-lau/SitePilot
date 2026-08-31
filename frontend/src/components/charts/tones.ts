/**
 * Shared chart color tokens. Tailwind's build-time scanner only picks up *complete* class name
 * strings in source — `` `stroke-${tone}` `` template interpolation is invisible to it and would
 * silently ship unstyled charts. Every chart component must look up its class through one of
 * these static maps instead of building a Tailwind class name dynamically.
 */

export type ChartTone = "chart-1" | "chart-2" | "chart-3" | "chart-4" | "chart-5" | "chart-6" | "success" | "danger" | "warning" | "accent" | "info" | "muted";

export const strokeClass: Record<ChartTone, string> = {
  "chart-1": "stroke-chart-1",
  "chart-2": "stroke-chart-2",
  "chart-3": "stroke-chart-3",
  "chart-4": "stroke-chart-4",
  "chart-5": "stroke-chart-5",
  "chart-6": "stroke-chart-6",
  success: "stroke-success",
  danger: "stroke-danger",
  warning: "stroke-warning",
  accent: "stroke-accent",
  info: "stroke-info",
  muted: "stroke-muted",
};

export const fillClass: Record<ChartTone, string> = {
  "chart-1": "fill-chart-1",
  "chart-2": "fill-chart-2",
  "chart-3": "fill-chart-3",
  "chart-4": "fill-chart-4",
  "chart-5": "fill-chart-5",
  "chart-6": "fill-chart-6",
  success: "fill-success",
  danger: "fill-danger",
  warning: "fill-warning",
  accent: "fill-accent",
  info: "fill-info",
  muted: "fill-muted",
};

export const textClass: Record<ChartTone, string> = {
  "chart-1": "text-chart-1",
  "chart-2": "text-chart-2",
  "chart-3": "text-chart-3",
  "chart-4": "text-chart-4",
  "chart-5": "text-chart-5",
  "chart-6": "text-chart-6",
  success: "text-success",
  danger: "text-danger",
  warning: "text-warning",
  accent: "text-accent",
  info: "text-info",
  muted: "text-muted",
};

export const bgClass: Record<ChartTone, string> = {
  "chart-1": "bg-chart-1",
  "chart-2": "bg-chart-2",
  "chart-3": "bg-chart-3",
  "chart-4": "bg-chart-4",
  "chart-5": "bg-chart-5",
  "chart-6": "bg-chart-6",
  success: "bg-success",
  danger: "bg-danger",
  warning: "bg-warning",
  accent: "bg-accent",
  info: "bg-info",
  muted: "bg-muted",
};

/** The 6-color categorical palette, in order, for multi-series charts (grouped bars, legends). */
export const CATEGORICAL_TONES: ChartTone[] = ["chart-1", "chart-2", "chart-3", "chart-4", "chart-5", "chart-6"];
