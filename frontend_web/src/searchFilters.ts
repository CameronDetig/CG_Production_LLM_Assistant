import type { FilterOption, FilterOptions, SearchFilters } from "./types";

export const EMPTY_FILTERS: SearchFilters = { shows: [], file_types: [] };
const STORAGE_KEY = "cg-assistant.filters";

export type FilterKey = keyof SearchFilters;

export const FILTER_GROUPS: { key: FilterKey; label: string }[] = [
  { key: "shows", label: "Shows" },
  { key: "file_types", label: "Asset types" },
];

/** Database values are lowercase with underscores ("cosmos_laundromat"); show them as words. */
export function formatFilterName(name: string): string {
  return name.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function countFilters(filters: SearchFilters): number {
  return filters.shows.length + filters.file_types.length;
}

/** One-line description of a selection, e.g. "Spring, Charge · Image". Empty when unfiltered. */
export function describeFilters(filters?: SearchFilters | null): string {
  if (!filters) return "";
  return FILTER_GROUPS.map(({ key }) => (filters[key] ?? []).map(formatFilterName).join(", "))
    .filter(Boolean)
    .join(" · ");
}

/** Drop selected values the backend no longer offers (a show was removed or renamed). */
export function pruneFilters(filters: SearchFilters, options: FilterOptions): SearchFilters {
  const keep = (values: string[], offered: FilterOption[]) =>
    values.filter((value) => offered.some((option) => option.name === value));
  return { shows: keep(filters.shows, options.shows), file_types: keep(filters.file_types, options.file_types) };
}

export function loadStoredFilters(): SearchFilters {
  try {
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "null") as Partial<SearchFilters> | null;
    const strings = (value: unknown) =>
      Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
    return { shows: strings(stored?.shows), file_types: strings(stored?.file_types) };
  } catch {
    return EMPTY_FILTERS;
  }
}

export function storeFilters(filters: SearchFilters): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(filters));
  } catch {
    // The selection still applies for this page load; it just will not be remembered.
  }
}
