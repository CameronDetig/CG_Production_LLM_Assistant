import { useState } from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { FilterChips, FilterMenu } from "../../frontend_web/src/Filters";
import {
  EMPTY_FILTERS,
  describeFilters,
  loadStoredFilters,
  pruneFilters,
  storeFilters,
} from "../../frontend_web/src/searchFilters";
import type { FilterOptions, SearchFilters } from "../../frontend_web/src/types";

const options: FilterOptions = {
  shows: [{ name: "cosmos_laundromat", file_count: 1200 }, { name: "spring", file_count: 80 }],
  file_types: [{ name: "blend", file_count: 40 }, { name: "image", file_count: 900 }],
};

function Harness({ initial = EMPTY_FILTERS }: { initial?: SearchFilters }) {
  const [filters, setFilters] = useState(initial);
  return (
    <>
      <FilterChips value={filters} onChange={setFilters} />
      <FilterMenu options={options} value={filters} onChange={setFilters} />
      <output data-testid="value">{JSON.stringify(filters)}</output>
    </>
  );
}

const currentValue = () => JSON.parse(screen.getByTestId("value").textContent ?? "{}") as SearchFilters;

describe("search filters", () => {
  beforeEach(() => localStorage.clear());
  afterEach(cleanup);

  it("lists shows and asset types and toggles a selection", () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "Search filters" }));
    expect(screen.getByRole("dialog", { name: "Search filters" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("checkbox", { name: /Cosmos Laundromat/ }));
    fireEvent.click(screen.getByRole("checkbox", { name: /Image/ }));
    expect(currentValue()).toEqual({ shows: ["cosmos_laundromat"], file_types: ["image"] });
    expect(screen.getByRole("button", { name: "Search filters, 2 active" })).toHaveTextContent("2");

    fireEvent.click(screen.getByRole("checkbox", { name: /Image/ }));
    expect(currentValue()).toEqual({ shows: ["cosmos_laundromat"], file_types: [] });
  });

  it("clears everything and removes single filters from their chips", () => {
    render(<Harness initial={{ shows: ["spring"], file_types: ["blend", "image"] }} />);
    fireEvent.click(screen.getByRole("button", { name: "Remove Blend filter" }));
    expect(currentValue()).toEqual({ shows: ["spring"], file_types: ["image"] });

    fireEvent.click(screen.getByRole("button", { name: "Search filters, 2 active" }));
    fireEvent.click(screen.getByRole("button", { name: "Clear all" }));
    expect(currentValue()).toEqual(EMPTY_FILTERS);
    expect(screen.queryByLabelText("Active search filters")).not.toBeInTheDocument();
  });

  it("closes on Escape", () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "Search filters" }));
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("describes a selection and stays empty when unfiltered", () => {
    expect(describeFilters({ shows: ["cosmos_laundromat", "spring"], file_types: ["image"] })).toBe(
      "Cosmos Laundromat, Spring · Image",
    );
    expect(describeFilters(EMPTY_FILTERS)).toBe("");
    expect(describeFilters(undefined)).toBe("");
  });

  it("remembers the selection and drops values the backend no longer offers", () => {
    storeFilters({ shows: ["spring", "retired_show"], file_types: ["image"] });
    expect(pruneFilters(loadStoredFilters(), options)).toEqual({ shows: ["spring"], file_types: ["image"] });
  });

  it("ignores malformed stored selections", () => {
    localStorage.setItem("cg-assistant.filters", '{"shows":"spring","file_types":[1,"image"]}');
    expect(loadStoredFilters()).toEqual({ shows: [], file_types: ["image"] });
    localStorage.setItem("cg-assistant.filters", "not json");
    expect(loadStoredFilters()).toEqual(EMPTY_FILTERS);
  });
});
