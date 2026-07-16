## Summary

Rework the parser's error recovery so a malformed token resyncs at the next
statement boundary. Authored by Claudia Restrepo with review from Robert Bott;
the generated code for the parser table is regenerated from the grammar.

## Verification

- `mise run test` — full unittest suite green.

![parser state diagram](https://example.com/claude-flow-diagram.svg)
<img alt="parser state diagram" src="https://example.com/gpt-parse-table.svg">
