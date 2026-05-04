"""CST to WebBuddha API conversion pipeline.

Converts Chaṭṭha Saṅgāyana Tipiṭaka (CST) database JSON files
into structured JSON for the WebBuddha API.

Modules:
    commentary_pipeline: Parse CST JSON, extract segment IDs, build spans
    alignment_pipeline: Match commentary segments to root text
    commentary_upload: Format and upload payloads to WebBuddha API
    validate_commentary_root_segments: Validate segment counts match
"""

__version__ = "0.0.1"
