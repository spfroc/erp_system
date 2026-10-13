import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it } from "vitest";

import { SearchableSelect } from "./App";

afterEach(() => {
  cleanup();
});

function SelectHarness() {
  const [value, setValue] = useState("");

  return (
    <SearchableSelect
      value={value}
      options={[
        { value: "service-a", label: "服务 A" },
        { value: "service-b", label: "服务 B" },
      ]}
      onChange={setValue}
      placeholder="请选择服务"
      ariaLabel="选择服务"
    />
  );
}

describe("SearchableSelect", () => {
  it("reopens the options when the selected value is clicked", () => {
    render(<SelectHarness />);

    const input = screen.getByRole("combobox", { name: "选择服务" });
    fireEvent.focus(input);
    fireEvent.mouseDown(screen.getByRole("button", { name: "服务 A" }));

    expect(input).toHaveValue("服务 A");
    expect(input).toHaveAttribute("aria-expanded", "false");

    fireEvent.click(input);

    expect(input).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("button", { name: "服务 B" })).toBeInTheDocument();
  });

  it("clears the selected value from the search field", () => {
    render(<SelectHarness />);

    const input = screen.getByRole("combobox", { name: "选择服务" });
    fireEvent.focus(input);
    fireEvent.mouseDown(screen.getByRole("button", { name: "服务 A" }));
    expect(input).toHaveValue("服务 A");

    fireEvent.mouseDown(screen.getByRole("button", { name: "清空选择服务" }));
    expect(input).toHaveValue("");
  });
});
