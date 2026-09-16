# Flow: ELI5 - fixture

CPP-specific wiring lives outside the markers and is not pinned.

<!-- eli5-core:begin (canonical: https://github.com/cooneycw/eli5-gate commands/eli5.md) -->
## What this is for

A miniature stand-in for the real gate core. Its CONTENT is irrelevant to
what this control asks; only whether the bytes match the pin is.
<!-- eli5-core:end -->

## Notes

- This bullet MENTIONS the <!-- eli5-core:begin --> marker mid-line on purpose:
  the real eli5.md does, and marker detection is anchored to the start of a
  line so prose cannot re-trigger the state machine. A fixture without this
  line would not exercise the anchoring at all.
