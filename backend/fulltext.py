from dataclasses import dataclass


@dataclass(frozen=True)
class ExtractedText:
    text: str
    source_basis: str


def extract_full_text(_pdf_url: str) -> ExtractedText:
    return ExtractedText(text="", source_basis="abstract_only")
