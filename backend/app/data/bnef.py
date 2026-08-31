"""BNEF Tier 1 PV module manufacturer registry. ARD §5.6 / §4.1 (BNEF check tool),
consumed by agents/quote_parser.py, agents/tools.py, routes/components.py.

Contract: ``match_manufacturer(name) -> (is_tier1, matched_name)``
  ``(True, canonical_name)``  - known BNEF Tier 1 manufacturer
  ``(False, canonical_name)`` - known Tier 2 (or otherwise non-Tier-1) manufacturer
  ``(None, None)``            - genuinely unknown / unmatched

Matching is fuzzy-normalised: punctuation, casing, and corporate suffixes
(Sdn Bhd, Co Ltd, GmbH, Inc, Pte, Ltd, Corporation, Corp, ...) are stripped
before comparison, so "LONGi Green Energy Technology Co., Ltd.", "Longi Solar"
and "LONGI" all resolve to the same registry entry.
"""
from __future__ import annotations

import re

# --------------------------------------------------------------------------
# Registry — canonical display name -> extra aliases (the canonical name
# itself is always indexed too, so it doesn't need to repeat in its list).
# ~40 real BNEF Tier 1 module manufacturers, per ARD D4 / §5.6.
# --------------------------------------------------------------------------

TIER1_MANUFACTURERS: dict[str, tuple[str, ...]] = {
    "LONGi Green Energy": ("LONGi", "LONGi Solar", "LONGi Green Energy Technology"),
    "Trina Solar": ("Trina", "Trina Solar Vertex", "Vertex"),
    "JA Solar": ("JASolar", "JA Solar Technology"),
    "Jinko Solar": ("Jinko", "JinkoSolar", "Jinko Solar Holding", "Tiger Neo"),
    "Canadian Solar": ("Canadian Solar Inc",),
    "Risen Energy": ("Risen", "Risen Solar Technology"),
    "Astronergy": ("Astro Energy", "Chint Astronergy"),
    "First Solar": (),
    "Qcells": ("Q Cells", "Q.Cells", "Hanwha Qcells", "Hanwha Q Cells"),
    "GCL System Integration": ("GCL", "GCL-SI", "GCL System"),
    "Tongwei Solar": ("Tongwei",),
    "DAS Solar": ("DAS",),
    "Boviet Solar": ("Boviet",),
    "Waaree Energies": ("Waaree",),
    "Vikram Solar": ("Vikram",),
    "Adani Solar": ("Adani",),
    "ZNShine Solar": ("ZNShine", "ZN Shine"),
    "Suntech Power": ("Suntech",),
    "HT-SAAE": ("Hengdian Group HT SAAE", "HT SAAE", "HTSAAE"),
    "Talesun Solar": ("Talesun",),
    "Phono Solar": ("Phono",),
    "Emmvee": ("Emmvee Photovoltaic Power",),
    "REC Group": ("REC Solar", "REC"),
    "Seraphim Energy": ("Seraphim",),
    "Yingli Solar": ("Yingli", "Yingli Green Energy"),
    "GLGET": ("Gokin Solar", "GLG Group"),
    "Chint Solar": ("Chint",),
    "Sunpower": ("SunPower", "Maxeon", "Maxeon Solar"),
    "Hansol Technics": ("Hansol",),
    "Shinsung E&G": ("Shinsung",),
    "Jolywood": ("Jolywood Solar",),
    "Meyer Burger": (),
    "Solar Space": ("SolarSpace",),
    "Ulica Solar": ("Ulica",),
    "Ecosolifer": (),
    "Tata Power Solar": ("Tata Solar",),
    "AE Solar": ("AE Solar Energy",),
    "Renesola": ("ReneSola",),
    "Grand Renewable Energy": ("Grand Renewable",),
    "Trienergy": ("Tri Energy",),
    "Longi (Malaysia)": (),  # local entity variant seen on some Malaysian quotes
}

# A handful of explicit Tier 2 names (real, commonly-quoted brands in the
# Malaysian market that are NOT on the BNEF Tier 1 list) so the UI can say
# "Tier 2" with a matched name rather than "unknown" for these.
TIER2_MANUFACTURERS: dict[str, tuple[str, ...]] = {
    "Sunport Power": ("Sunport",),
    "Amerisolar": (),
    "Eurener": (),
    "Perlight Solar": ("Perlight",),
    "Topray Solar": ("Topray",),
    "Sunrise Energy": (),
    "Goldi Solar": ("Goldi",),
}

_CORP_SUFFIXES = (
    "sdn bhd", "bhd", "pte ltd", "pte",
    "co ltd", "company limited", "corporation",
    "corp", "gmbh", "inc", "incorporated", "llc", "ltd", "limited",
    "holding", "holdings", "technology", "technologies", "group",
    "power", "energy", "solar", "photovoltaic", "pv", "new energy",
)

_PUNCT_RE = re.compile(r"[.,()&/\\-]+")
_WS_RE = re.compile(r"\s+")


def _normalise(name: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace, then repeatedly
    strip a trailing corporate-suffix word/phrase so "LONGi Green Energy
    Technology Co., Ltd." reduces toward "longi green"."""
    s = name.strip().lower()
    s = _PUNCT_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip()

    changed = True
    while changed:
        changed = False
        for suffix in sorted(_CORP_SUFFIXES, key=len, reverse=True):
            if s == suffix:
                break
            if s.endswith(" " + suffix):
                s = s[: -(len(suffix) + 1)].strip()
                changed = True
                break
    return s


def _build_index(registry: dict[str, tuple[str, ...]]) -> dict[str, str]:
    index: dict[str, str] = {}
    for canonical, aliases in registry.items():
        for key in (canonical, *aliases):
            norm = _normalise(key)
            if norm:
                index[norm] = canonical
    return index


_TIER1_INDEX = _build_index(TIER1_MANUFACTURERS)
_TIER2_INDEX = _build_index(TIER2_MANUFACTURERS)


def match_manufacturer(name: str | None) -> tuple[bool | None, str | None]:
    """ARD §5.6 ``check_bnef_tier`` tool / §5.1 ``GET /api/bnef/check`` contract.

    Returns ``(is_tier1, matched_name)``:
      ``(True, canonical)``  - matched a BNEF Tier 1 manufacturer
      ``(False, canonical)`` - matched a known Tier 2 manufacturer
      ``(None, None)``       - no match (genuinely unknown, or name was empty)
    """
    if not name or not name.strip():
        return None, None

    norm = _normalise(name)
    if not norm:
        return None, None

    if norm in _TIER1_INDEX:
        return True, _TIER1_INDEX[norm]
    if norm in _TIER2_INDEX:
        return False, _TIER2_INDEX[norm]

    # Substring fallback: a normalised quote string sometimes carries extra
    # words we didn't anticipate (model number, "module", etc.) — if a
    # registry key is a whole-word-ish substring of the input (or vice
    # versa), treat it as a match. Guarded to keys of at least 4 chars to
    # avoid spurious short-token collisions.
    for norm_key, canonical in _TIER1_INDEX.items():
        if len(norm_key) >= 4 and (norm_key in norm or norm in norm_key):
            return True, canonical
    for norm_key, canonical in _TIER2_INDEX.items():
        if len(norm_key) >= 4 and (norm_key in norm or norm in norm_key):
            return False, canonical

    return None, None
