import { describe, it, expect } from "vitest";
import { intervalStyle, stamp } from "../lib/format";
describe("UTC timeline", () => {
  it("keeps explicit UTC across timezone offsets", () =>
    expect(stamp("2024-05-10T15:00:00+03:00")).toContain("12:00"));
  it("positions half-window intervals", () =>
    expect(
      intervalStyle(
        "2024-05-10T01:00Z",
        "2024-05-10T02:00Z",
        "2024-05-10T00:00Z",
        "2024-05-10T02:00Z",
      ),
    ).toEqual({ left: "50%", width: "50%" }));
  it("does not display missing date as epoch", () =>
    expect(stamp(null)).toBe("Не предоставлено"));
  it("treats timezone-free OMM epoch as UTC per source schema", () =>
    expect(stamp("2026-09-18T03:25:38.782272")).toContain("03:25"));
});
