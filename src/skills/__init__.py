"""Skills for analyzing book research materials."""

from src.skills.annotation_aggregator import AnnotationAggregator
from src.skills.citation_manager import CitationManager
from src.skills.fact_extractor import FactExtractor
from src.skills.gap_analyzer import ResearchGapDetector
from src.skills.outline_analyzer import OutlineAnalyzer
from src.skills.similarity_detector import SimilarityDetector

__all__ = [
    "FactExtractor",
    "CitationManager",
    "ResearchGapDetector",
    "OutlineAnalyzer",
    "AnnotationAggregator",
    "SimilarityDetector",
]
