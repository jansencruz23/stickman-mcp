# Creative work lives in host Claude; MCP tools stay mechanical

The MCP server never calls an LLM. Claude — the MCP host, running under the creator's Claude subscription — writes the Script, the Image Prompts, and the Video Package metadata in-conversation, then drives dumb tools (TTS, image generation, rendering). This answers the "can we use the subscription instead of an API?" question with yes by construction: the only LLM in the system is the host itself, at zero marginal cost.

## Considered Options

- Self-contained `create_video(topic)` tool with Ollama inside the server: fully autonomous from a single call, but caps creative quality at a local model, adds LLM plumbing to the server, and was the only reason an LLM dependency existed. Rejected. (MCP "sampling" — the server asking the host for completions — is unsupported by Claude Code/Desktop and deprecated in the MCP spec, so it was not a viable middle ground.)

## Consequences

- Script quality rides on the host model and the `/produce-video` skill's instructions, not on server code.
- The server has no LLM credentials, no model config, and works identically under subscription or API billing.
- Fully headless runs still work (`claude -p` honors MCP servers under a subscription); they do not require moving intelligence into the server.
