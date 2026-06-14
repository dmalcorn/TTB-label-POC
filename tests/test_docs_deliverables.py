"""Documentation-deliverable contract tests (Story 6.3, AC-1 / AC-2 / AC-3 / AC-4).

Pins the FR-26 / NFR-2 / NFR-5 deliverable contract that can be checked WITHOUT
running the app — a pure text-file audit of the repo's documentation surfaces:

- **AC-1** — ``README.md`` provides setup/run instructions and links every
  brief-mandated ``docs/`` deliverable, and every such link resolves to a file
  that exists (no dangling deliverable link). The generalized no-dangling-link
  check extends to all in-repo relative links in ``README.md`` and ``docs/index.md``.
- **AC-2** — ``docs/outbound-calls-inventory.md`` enumerates every external call
  with the fixed 3-way classification (``none`` / ``local`` /
  ``models-internal-endpoint``), names the ``app/adapters/llm`` off-host boundary,
  and is framed as a delivered artifact (not an incomplete planning artifact).
- **AC-3** — the README's run path is self-contained and carries no stale
  "completes in a later epic" disclaimer.
- **AC-4** — the headline limitations (font/dimension size not checked, mock /
  seeded / no-PII data, prototype/POC status) are documented beside the
  capabilities (NFR-5).

Mirrors the repo-file-reading idiom in ``tests/test_deploy_config.py``.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
README = REPO_ROOT / "README.md"
DOCS_INDEX = REPO_ROOT / "docs" / "index.md"
OUTBOUND_INVENTORY = REPO_ROOT / "docs" / "outbound-calls-inventory.md"

# The brief-mandated docs/ deliverables the README must link (FR-26).
REQUIRED_DELIVERABLES = (
    "docs/approach.md",
    "docs/tools-used.md",
    "docs/assumptions.md",
    "docs/tradeoffs-and-limitations.md",
    "docs/presearch.md",
    "docs/data-dictionary.md",
    "docs/image-handling.md",
    "docs/regulatory-rules-distilled-spirits.md",
    "docs/regulatory-rules-wine.md",
    "docs/regulatory-rules-beer.md",
    "docs/label-requirements-by-type.md",
    "docs/applicant-workflow-distilled-spirits.md",  # landscape / COLAs Online workflow
    "docs/ux-design-notes.md",  # USWDS-compliance notes (§10)
    "docs/outbound-calls-inventory.md",
)

# Fixed NFR-2 classification vocabulary.
CLASSIFICATIONS = ("none", "local", "models-internal-endpoint")

# Matches a markdown link target: [text](target)
_MD_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _relative_link_targets(markdown: str) -> list[str]:
    """In-repo relative link targets — skip http(s), mailto, and pure anchors."""
    targets: list[str] = []
    for raw in _MD_LINK.findall(markdown):
        target = raw.strip()
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        # Drop any trailing #anchor on a file link.
        target = target.split("#", 1)[0]
        if target:
            targets.append(target)
    return targets


# ── AC-1: README links every required deliverable; each resolves ─────────────


def test_readme_exists() -> None:
    assert README.is_file(), "README.md must exist at the repo root"


def test_readme_links_every_required_deliverable() -> None:
    readme = _read(README)
    missing = [d for d in REQUIRED_DELIVERABLES if d not in readme]
    assert not missing, f"README.md does not link required deliverable(s): {missing}"


def test_every_required_deliverable_file_exists() -> None:
    missing = [d for d in REQUIRED_DELIVERABLES if not (REPO_ROOT / d).is_file()]
    assert not missing, f"Required deliverable file(s) missing on disk: {missing}"


def test_readme_has_setup_and_run_instructions() -> None:
    readme = _read(README)
    # Configure step, a docker build/run command, and the offline smoke test.
    assert ".env.example" in readme, "README must document the .env.example configure step"
    assert "docker" in readme.lower(), "README must give a docker build/run command"
    assert "--network none" in readme, "README must document the offline zero-egress smoke test"


def test_readme_relative_links_resolve() -> None:
    readme = _read(README)
    dangling = [t for t in _relative_link_targets(readme) if not (REPO_ROOT / t).exists()]
    assert not dangling, f"README.md has dangling relative link(s): {dangling}"


def test_docs_index_relative_links_resolve() -> None:
    index = _read(DOCS_INDEX)
    base = DOCS_INDEX.parent
    dangling = [t for t in _relative_link_targets(index) if not (base / t).exists()]
    assert not dangling, f"docs/index.md has dangling relative link(s): {dangling}"


# ── AC-2: outbound-call inventory — 3-way classified, finalized ──────────────


def test_outbound_inventory_exists() -> None:
    assert OUTBOUND_INVENTORY.is_file()


def test_outbound_inventory_has_three_way_classification() -> None:
    inventory = _read(OUTBOUND_INVENTORY)
    # Assert each token appears as a backtick-quoted classification label, not as an
    # incidental English substring ("none"/"local" are common words; the backtick form
    # is the genuine discriminator that pins the NFR-2 classification scheme).
    missing = [c for c in CLASSIFICATIONS if f"`{c}`" not in inventory]
    assert not missing, (
        f"outbound-calls-inventory.md missing backtick-quoted classification token(s): {missing}"
    )


def test_outbound_inventory_names_the_offhost_boundary() -> None:
    inventory = _read(OUTBOUND_INVENTORY)
    assert "app/adapters/llm" in inventory, (
        "the inventory must name the only off-host boundary: app/adapters/llm/*"
    )


def test_outbound_inventory_is_a_delivered_artifact() -> None:
    inventory = _read(OUTBOUND_INVENTORY)
    # Match regardless of markdown bolding/extra spacing on the Status: line.
    normalized = re.sub(r"[*\s]+", " ", inventory)
    # Negative: not framed as an incomplete planning artifact awaiting build-out.
    assert "Status: Planning artifact" not in normalized, (
        "the inventory must be finalized as a delivered artifact, not a planning artifact"
    )
    # Positive: the Status: line must affirmatively mark the artifact delivered, so the
    # test pins delivered-ness (not merely the absence of one stale phrase — a missing or
    # 'Draft' status line must not pass).
    assert "Status: Delivered" in normalized, (
        "the inventory's Status: line must affirmatively mark it Delivered"
    )


# ── AC-3: clone-and-run from README alone — no stale 'later epic' disclaimer ──


def test_readme_has_no_stale_later_epic_disclaimer() -> None:
    readme = _read(README)
    stale_markers = (
        "completes in Epic 6",
        "remaining deliverables completes",
        "population of the remaining deliverables",
    )
    found = [m for m in stale_markers if m in readme]
    assert not found, (
        f"README still carries a stale 'deliverables complete later' disclaimer: {found}"
    )


# ── AC-4: limitations documented beside capabilities (NFR-5) ─────────────────


def test_readme_documents_font_size_limitation() -> None:
    # Pin the contiguous claim (bold/space-insensitive) so two unrelated substrings
    # ("font" … "not checked") elsewhere in the README cannot co-satisfy it.
    readme = re.sub(r"[*\s]+", " ", _read(README)).lower()
    assert "font/dimension size is not checked" in readme, (
        "README must state the font/dimension-size-not-checked limitation as one claim"
    )


def test_readme_documents_data_and_prototype_limits() -> None:
    readme = _read(README)
    assert "no PII" in readme or "No PII" in readme, (
        "README must state the no-PII / mock-data limit"
    )
    lowered = readme.lower()
    assert "proof of concept" in lowered or "proof-of-concept" in lowered, (
        "README must state the prototype / proof-of-concept status"
    )


def test_tradeoffs_doc_states_headline_limitations() -> None:
    # AC-4 binds all three headline limits to the tradeoffs doc (not only the README):
    # font/dimension not checked, mock/seeded no-PII data, and prototype/POC status.
    tradeoffs = _read(REPO_ROOT / "docs" / "tradeoffs-and-limitations.md").lower()
    assert "font" in tradeoffs, "tradeoffs-and-limitations.md must cover the font-size limitation"
    assert "no pii" in tradeoffs or "seeded" in tradeoffs, (
        "tradeoffs-and-limitations.md must cover the mock/seeded/no-PII data limitation"
    )
    assert "proof of concept" in tradeoffs or "proof-of-concept" in tradeoffs, (
        "tradeoffs-and-limitations.md must state the prototype / proof-of-concept status"
    )
