import { describe, expect, it } from "vitest";
import { app } from "../src/server.js";

describe("server", () => {
  it("answers /api/health", async () => {
    const server = app.listen(0);
    const { port } = server.address() as { port: number };
    const res = await fetch(`http://localhost:${port}/api/health`);
    server.close();
    expect(res.status).toBe(200);
    expect((await res.json()).ok).toBe(true);
  });
});
