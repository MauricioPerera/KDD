// search_knowledge — universal origin-memory search tool (llms-skills memory).
// Identical for every publisher: its sha256 is a stable, ecosystem-wide constant.
registerTool({
  name: "search_knowledge",
  description: "BM25 search over this origin's published knowledge (OKF bundle). Returns the most relevant chunks with concept ids.",
  inputSchema: { type: "object", properties: { q: { type: "string", description: "search query" }, k: { type: "number", description: "max results (1-10, default 5)" } }, required: ["q"] },
  handler: async function (args) {
    return await host.memorySearch(args.q, typeof args.k === "number" ? args.k : 5);
  }
});
