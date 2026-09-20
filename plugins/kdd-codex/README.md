# KDD for Codex

This plugin supplies the `kdd-workflow` skill and optional lifecycle hooks.

To enable delivery, configure `KDD_WEBHOOK_URL` with an HTTPS relay endpoint and
`KDD_WEBHOOK_SECRET` with a high-entropy shared secret in the host environment.
The relay must verify `X-KDD-Signature` before accepting an event. Without both
variables, hooks exit successfully and send no network request.

The event payload contains only an event name, session identifier, and working
directory. It never includes prompts, tool arguments, file contents, or secrets.
Review and trust the plugin hooks in Codex before enabling them.
