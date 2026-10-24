// Render tests for the reusable Card container (Req 2.2, 6.5).
//
// Card is presentational only, so these are plain render tests: it renders its
// title, renders its children, and applies the `card` class. No Router or data
// providers are needed because Card holds no data logic.

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import Card from "./Card";

describe("Card", () => {
  it("renders the title as a heading", () => {
    render(<Card title="Top Finding" />);
    expect(
      screen.getByRole("heading", { name: "Top Finding" })
    ).toBeInTheDocument();
  });

  it("renders its children", () => {
    render(
      <Card title="Study Counts">
        <p>wrapped page content</p>
      </Card>
    );
    expect(screen.getByText("wrapped page content")).toBeInTheDocument();
  });

  it("applies the card class to its container", () => {
    const { container } = render(
      <Card title="Method and Sources">
        <p>body</p>
      </Card>
    );
    const section = container.querySelector("section");
    expect(section).not.toBeNull();
    expect(section).toHaveClass("card");
  });

  it("appends an extra className alongside the base card class", () => {
    const { container } = render(<Card className="home-card">content</Card>);
    const section = container.querySelector("section");
    expect(section).toHaveClass("card");
    expect(section).toHaveClass("home-card");
  });

  it("omits the title heading when no title is provided", () => {
    render(
      <Card>
        <p>no title here</p>
      </Card>
    );
    expect(screen.queryByRole("heading")).toBeNull();
    expect(screen.getByText("no title here")).toBeInTheDocument();
  });
});
