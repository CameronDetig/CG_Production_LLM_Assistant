import { useEffect, useRef, useState } from "react";
import { SlidersHorizontal, X } from "lucide-react";
import { EMPTY_FILTERS, FILTER_GROUPS, countFilters, formatFilterName } from "./searchFilters";
import type { FilterOptions, SearchFilters } from "./types";

function toggled(values: string[], name: string): string[] {
  return values.includes(name) ? values.filter((value) => value !== name) : [...values, name];
}

interface FilterProps {
  options: FilterOptions | null;
  value: SearchFilters;
  onChange: (filters: SearchFilters) => void;
}

/** Composer button that opens the show / asset type checkbox lists. */
export function FilterMenu({ options, value, onChange, disabled }: FilterProps & { disabled?: boolean }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const active = countFilters(value);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div className="filter-menu" ref={rootRef}>
      <button
        type="button"
        className={`filter-button ${active ? "active" : ""}`}
        onClick={() => setOpen((current) => !current)}
        disabled={disabled}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label={active ? `Search filters, ${active} active` : "Search filters"}
        title="Limit the search to specific shows or asset types"
      >
        <SlidersHorizontal size={19} />
        {active > 0 && <span className="filter-badge">{active}</span>}
      </button>
      {open && (
        <div className="filter-popover" role="dialog" aria-label="Search filters">
          <div className="filter-popover-head">
            <strong>Search in</strong>
            <button type="button" onClick={() => onChange(EMPTY_FILTERS)} disabled={!active}>Clear all</button>
          </div>
          {!options ? (
            <p className="muted">Filters are unavailable right now.</p>
          ) : (
            <div className="filter-groups">
              {FILTER_GROUPS.map(({ key, label }) => (
                <fieldset key={key}>
                  <legend>{label}<span>{value[key].length ? `${value[key].length} selected` : "All"}</span></legend>
                  <div className="filter-options">
                    {options[key].map((option) => (
                      <label key={option.name}>
                        <input
                          type="checkbox"
                          checked={value[key].includes(option.name)}
                          onChange={() => onChange({ ...value, [key]: toggled(value[key], option.name) })}
                        />
                        <span>{formatFilterName(option.name)}</span>
                        <small>{option.file_count.toLocaleString()}</small>
                      </label>
                    ))}
                    {!options[key].length && <p className="muted">None found.</p>}
                  </div>
                </fieldset>
              ))}
            </div>
          )}
          <p className="filter-hint">Nothing ticked in a list means that list is not limited.</p>
        </div>
      )}
    </div>
  );
}

/** Removable chips for the active selection, shown above the composer. */
export function FilterChips({ value, onChange }: Pick<FilterProps, "value" | "onChange">) {
  if (!countFilters(value)) return null;
  return (
    <div className="filter-chips" aria-label="Active search filters">
      {FILTER_GROUPS.flatMap(({ key }) =>
        value[key].map((name) => (
          <span className="filter-chip" key={`${key}-${name}`}>
            {formatFilterName(name)}
            <button
              type="button"
              onClick={() => onChange({ ...value, [key]: value[key].filter((item) => item !== name) })}
              aria-label={`Remove ${formatFilterName(name)} filter`}
            >
              <X size={13} />
            </button>
          </span>
        )),
      )}
    </div>
  );
}
