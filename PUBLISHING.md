# Publishing KDD Pages

GitHub Pages serves the root of `gh-pages` at
`https://mauricioperera.github.io/KDD/`. The canonical methodology source is
the `main` branch. This branch is a published copy, not the source of truth.

1. Copy `main:knowledge/` into `gh-pages:knowledge/`, preserving paths and
   bytes. Copy the linked public supporting material in `docs/reports/`,
   `.agents/`, and `examples/quality-approval/` plus
   `examples/modelar-verification/`. Keep the four `knowledge/**/index.html`
   directory pages so Markdown links to those directories resolve.
2. Regenerate the search bundle with
   `npx -y @rckflr/llms-skills@0.4.1 memory knowledge --root .`.
3. In `llms-skills.json`, prefix each published `url`, `tool_url`, and
   `memory.snapshot_url` with `/KDD/`. The `memory` command writes root-relative
   URLs, which point outside this GitHub project page.
4. Run `npx -y @rckflr/llms-skills@0.4.1 publish --root .`, then
   `npx -y @rckflr/llms-skills@0.4.1 publish --check --root .`. Serve the
   checkout locally under `/KDD/` and run
   `npx -y @rckflr/llms-skills@0.4.1 validate <local-or-live-/KDD/llms.txt> --strict`.
5. Update the landing page's dated figures from the current `main` source and
   CI evidence. Check all internal links and the EN/ES/PT language controls.
   Merge into `gh-pages`, wait for the Pages build, and verify the live URLs.

`memory --check` currently reports manifest drift after step 3 because it
expects its own root-relative `snapshot_url`; use the prefixed-site validation
and `publish --check` as the publication checks. The declared `demo_seed` is
public and provides reproducible signatures, not private-key authentication.
