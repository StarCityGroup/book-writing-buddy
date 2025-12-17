"""Smart Quote & Fact Extraction Skill.

Identifies and extracts notable quotes, statistics, and facts from sources.
"""

import re
from typing import Any, Dict, List


class FactExtractor:
    """Extract facts, quotes, and statistics from text."""

    def __init__(self):
        """Initialize fact extractor with patterns."""
        # Regex patterns for fact types
        self.stat_pattern = r"\d+[\d,\.]*\s*(?:%|percent|billion|million|thousand|USD|dollars?|GB|TB|MB|Mbps|Gbps)"
        self.quote_pattern = r'["\u201C]([^"\u201D]{20,200})["\u201D]'
        self.definition_pattern = (
            r"(?:is defined as|refers to|means|is a type of|is known as)"
        )
        self.case_study_pattern = r"(?:in the case of|for example|for instance|such as)"

    def extract_facts(
        self, text: str, metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract facts from text chunk.

        Args:
            text: Text to analyze
            metadata: Metadata about the source

        Returns:
            List of fact dictionaries with type, value, and context
        """
        facts = []

        # Find statistics
        for match in re.finditer(self.stat_pattern, text, re.IGNORECASE):
            facts.append(
                {
                    "type": "statistic",
                    "value": match.group(),
                    "context": text[max(0, match.start() - 50) : match.end() + 50],
                    **metadata,
                }
            )

        # Find quotes
        for match in re.finditer(self.quote_pattern, text):
            quote_text = match.group(1)
            # Skip if quote is too short or generic
            if len(quote_text) > 30:
                facts.append(
                    {
                        "type": "quote",
                        "value": quote_text,
                        "context": text[max(0, match.start() - 50) : match.end() + 50],
                        **metadata,
                    }
                )

        # Check for definitions
        if re.search(self.definition_pattern, text, re.IGNORECASE):
            # Extract the sentence containing the definition
            sentences = text.split(". ")
            for sentence in sentences:
                if re.search(self.definition_pattern, sentence, re.IGNORECASE):
                    facts.append(
                        {
                            "type": "definition",
                            "value": sentence.strip(),
                            **metadata,
                        }
                    )
                    break

        # Check for case studies/examples
        if re.search(self.case_study_pattern, text, re.IGNORECASE):
            facts.append(
                {
                    "type": "case_study",
                    "value": text[:300],  # First 300 chars
                    **metadata,
                }
            )

        return facts

    def extract_and_tag_chunk(
        self, text: str, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract facts and add tags to chunk metadata.

        Args:
            text: Chunk text
            metadata: Chunk metadata

        Returns:
            Updated metadata with fact tags
        """
        facts = self.extract_facts(text, {})

        # Add fact tags to metadata
        if facts:
            metadata["has_facts"] = True
            metadata["fact_types"] = list({f["type"] for f in facts})
            metadata["fact_count"] = len(facts)

        return metadata
