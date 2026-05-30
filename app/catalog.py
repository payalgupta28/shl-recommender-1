"""
catalog.py
==========
Loads the scraped SHL catalog (data/catalog.json) into memory once at startup
and offers small helpers the rest of the app needs:

  - the full list of assessments,
  - a name -> assessment lookup (so the LLM can only ever return real items),
  - a compact text "document" per assessment for the retrieval index.

This is the single source of truth for what is "in the catalog". Because the
LLM is only allowed to pick from these names, every URL we return is guaranteed
to come from the real scraped catalog (an SHL hard requirement).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "catalog.json"

# Human-readable expansion of SHL's single-letter test types. We fold these
# words into each assessment's search document so a query like "personality
# test" matches P-type items even if the word "personality" isn't in the title.
TEST_TYPE_WORDS = {
    "A": "ability aptitude cognitive reasoning numerical verbal inductive",
    "B": "biodata situational judgement judgment behavioural scenario",
    "C": "competency competencies skills framework",
    "D": "development 360 feedback growth",
    "E": "assessment exercise centre center role-play",
    "K": "knowledge skills technical programming coding language tool",
    "P": "personality behaviour behavior trait motivation work-style opq",
    "S": "simulation simulated practical hands-on coding task",
}


def normalize(name: str) -> str:
    """Loose key for matching names case/space/punctuation-insensitively."""
    return re.sub(r"[^a-z0-9]+", "", name.lower())


@dataclass
class Assessment:
    name: str
    url: str
    test_type: list[str]
    remote_testing: bool = False
    adaptive_irt: bool = False
    description: str = ""
    job_levels: str = ""

    @property
    def test_type_str(self) -> str:
        """Join letters the way the SHL response example does: 'A, P'."""
        return ", ".join(self.test_type)

    def search_document(self) -> str:
        """The text the retriever indexes. Name is repeated to weight it higher."""
        type_words = " ".join(TEST_TYPE_WORDS.get(t, "") for t in self.test_type)
        return " ".join([
            self.name, self.name,           # double weight on the title
            self.job_levels,
            self.description,
            type_words,
        ]).strip()


@dataclass
class Catalog:
    items: list[Assessment]
    _by_norm: dict[str, Assessment] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Last-write-wins is fine; names are effectively unique in the catalog.
        self._by_norm = {normalize(a.name): a for a in self.items}

    def __len__(self) -> int:
        return len(self.items)

    def get(self, name: str) -> Assessment | None:
        """Resolve an LLM-provided name back to a real catalog entry."""
        return self._by_norm.get(normalize(name))

    @classmethod
    def load(cls, path: Path = DATA_FILE) -> "Catalog":
        if not path.exists():
            raise FileNotFoundError(
                f"Catalog not found at {path}. Run: python scripts/scrape_catalog.py"
            )
        raw = json.loads(path.read_text(encoding="utf-8"))
        items = [
            Assessment(
                name=r["name"],
                url=r["url"],
                test_type=r.get("test_type", []),
                remote_testing=r.get("remote_testing", False),
                adaptive_irt=r.get("adaptive_irt", False),
                description=r.get("description", ""),
                job_levels=r.get("job_levels", ""),
            )
            for r in raw
        ]
        return cls(items=items)
