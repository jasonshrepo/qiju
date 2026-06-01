# kedu-search — Query Kedu Records

Use this skill when prior session context would help answer or continue work.

1. Default to `--scope current_project`.
2. Widen to `--scope all` only when the user asks a cross-project question.
3. Convert the question into structured filters plus lexical terms.
4. Add `--agent <agent>` when the user wants records written by a specific agent.
5. Run `kedu search --scope <scope> --query "<terms>"`.
6. If results are incomplete, reformulate with aliases and related terms.
7. Use `kedu show <id>` when you only need to hydrate one candidate.

Kedu search identifies candidates. The model decides relevance for the current turn.
