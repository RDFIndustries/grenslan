"""One minimal schema-valid request per tool, for negative tests that add a single defect."""

from __future__ import annotations

from typing import Any

URI = "grenslan://artifacts/fixture"
RESOURCE = "grenslan://artifacts/fixture-capture"

MINIMAL_REQUESTS: dict[str, dict[str, Any]] = {
    "artifact_get": {"artifact_uri": URI},
    "browser_interact": {
        "browser_session_id": "b1",
        "page_state_id": "p1",
        "action": {"type": "click", "element_id": "e1"},
    },
    "browser_navigate": {"browser_session_id": "b1", "url": "https://example.org/"},
    "browser_observe": {"browser_session_id": "b1"},
    "browser_screenshot": {"browser_session_id": "b1", "page_state_id": "p1"},
    "browser_session_close": {"browser_session_id": "b1"},
    "browser_session_create": {},
    "capabilities_get": {},
    "citation_get": {"citation_id": "c1"},
    "document_find": {"artifact_uri": URI, "query": "fixture"},
    "document_inspect": {"artifact_uri": URI},
    "document_media": {"artifact_uri": URI},
    "document_open": {"artifact_uri": URI},
    "document_read": {"artifact_uri": URI},
    "document_render": {"artifact_uri": URI, "selection": {"pages": [1]}},
    "document_tables": {"artifact_uri": URI},
    "image_inspect": {"artifact_uri": URI},
    "image_ocr": {"artifact_uri": URI},
    "image_open": {"artifact_uri": URI},
    "image_search": {"query": "fixture"},
    "image_transform": {"artifact_uri": URI, "operation": "rotate", "degrees": 90},
    "operation_cancel": {"operation_id": "op1"},
    "operation_results": {"operation_id": "op1"},
    "operation_status": {"operation_id": "op1"},
    "quotation_verify": {"artifact_uri": URI, "quotation": "fixture"},
    "source_verify": {"artifact_uri": URI, "mode": "integrity"},
    "web_find": {"resource_uri": RESOURCE, "query": "fixture"},
    "web_links": {"resource_uri": RESOURCE},
    "web_open": {"url": "https://example.org/"},
    "web_read": {"resource_uri": RESOURCE},
    "web_search": {"query": "fixture"},
    "web_traverse": {"url": "https://example.org/", "max_depth": 1, "max_pages": 1},
}
