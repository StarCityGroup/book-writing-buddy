"""Test new BookRAG analysis methods."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_vectordb():
    """Fixture to mock VectorDBClient."""
    with patch("src.vectordb.client.VectorDBClient") as mock:
        mock_client = MagicMock()
        mock.return_value = mock_client
        yield mock_client


@pytest.fixture
def rag(mock_vectordb):
    """Fixture to create BookRAG instance with mocked vector DB."""
    from src.rag import BookRAG

    rag_instance = BookRAG()
    rag_instance.vectordb = mock_vectordb
    return rag_instance


def create_mock_search_results(chapter: int, count: int = 5):
    """Create mock search results for testing."""
    results = []
    for i in range(count):
        results.append(
            MagicMock(
                score=0.9 - (i * 0.05),
                payload={
                    "text": f"Test content {i}",
                    "chapter_number": chapter,
                    "chapter_title": f"Chapter {chapter}",
                    "source_type": "zotero" if i % 2 == 0 else "scrivener",
                    "title": f"Test Source {i}",
                    "item_type": "book" if i % 3 == 0 else "article",
                    "indexed_at": "2024-12-01T10:00:00Z",
                },
            )
        )
    return results


def test_cross_chapter_themes(rag, mock_vectordb):
    """Test cross-chapter theme tracking."""
    print("\n🧪 Testing Cross-Chapter Theme Tracking\n")

    # Mock scroll results for multiple chapters
    chapter_results = {
        3: create_mock_search_results(3, count=3),
        5: create_mock_search_results(5, count=2),
        9: create_mock_search_results(9, count=4),
    }

    def mock_scroll(collection_name, scroll_filter, limit, with_payload, with_vectors):
        # Return results based on chapter filter
        if "match" in scroll_filter["must"][0]:
            chapter_num = scroll_filter["must"][0]["match"]["value"]
            return (chapter_results.get(chapter_num, []), None)
        return ([], None)

    mock_vectordb.scroll.side_effect = mock_scroll

    # Test theme tracking
    results = rag.find_cross_chapter_themes("resilience", min_chapters=2)

    # Verify results structure
    assert "keyword" in results
    assert results["keyword"] == "resilience"
    assert "total_chapters" in results
    assert "total_mentions" in results
    assert "meets_threshold" in results
    assert "chapters" in results

    print(f"✅ Theme tracked across {results['total_chapters']} chapters")
    print(f"✅ Total mentions: {results['total_mentions']}")
    print(f"✅ Meets threshold: {results['meets_threshold']}")


def test_compare_chapters(rag, mock_vectordb):
    """Test chapter comparison."""
    print("\n🧪 Testing Chapter Comparison\n")

    # Mock scroll results for two chapters
    chapter1_results = create_mock_search_results(3, count=10)
    chapter2_results = create_mock_search_results(7, count=15)

    def mock_scroll(collection_name, scroll_filter, limit, with_payload, with_vectors):
        chapter_num = scroll_filter["must"][0]["match"]["value"]
        if chapter_num == 3:
            return (chapter1_results, None)
        elif chapter_num == 7:
            return (chapter2_results, None)
        return ([], None)

    mock_vectordb.scroll.side_effect = mock_scroll

    # Test comparison
    results = rag.compare_chapters(3, 7)

    # Verify results structure
    assert "chapter1" in results
    assert "chapter2" in results
    assert "comparison" in results

    assert results["chapter1"]["total_chunks"] >= 0
    assert results["chapter2"]["total_chunks"] >= 0
    assert "more_sources" in results["comparison"]
    assert "more_research_dense" in results["comparison"]

    print(f"✅ Chapter 3 chunks: {results['chapter1']['total_chunks']}")
    print(f"✅ Chapter 7 chunks: {results['chapter2']['total_chunks']}")
    print("✅ Comparison completed successfully")


def test_source_diversity(rag, mock_vectordb):
    """Test source diversity analysis."""
    print("\n🧪 Testing Source Diversity Analysis\n")

    # Create diverse sources
    mixed_results = []
    source_types = ["book", "article", "webpage", "book", "article"]
    for i, stype in enumerate(source_types):
        mixed_results.append(
            MagicMock(
                payload={
                    "chapter_number": 5,
                    "source_type": "zotero",
                    "title": f"Source {i}",
                    "item_type": stype,
                }
            )
        )

    mock_vectordb.scroll.return_value = (mixed_results, None)

    # Test diversity analysis
    results = rag.analyze_source_diversity(5)

    # Verify results structure
    assert "total_sources" in results
    assert "source_types" in results
    assert "diversity_score" in results
    assert "most_cited" in results
    assert "least_cited" in results

    assert 0 <= results["diversity_score"] <= 1
    print(f"✅ Total sources: {results['total_sources']}")
    print(f"✅ Diversity score: {results['diversity_score']:.2f}")
    print(f"✅ Source types: {results['source_types']}")


def test_identify_key_sources(rag, mock_vectordb):
    """Test key source identification."""
    print("\n🧪 Testing Key Source Identification\n")

    # Create results with repeated sources
    repeated_sources = []
    for i in range(15):
        source_num = i % 3  # Three sources, repeated
        repeated_sources.append(
            MagicMock(
                payload={
                    "chapter_number": 9,
                    "source_type": "zotero",
                    "title": f"Source {source_num}",
                    "item_type": "book" if source_num == 0 else "article",
                }
            )
        )

    mock_vectordb.scroll.return_value = (repeated_sources, None)

    # Test key source identification
    results = rag.identify_key_sources(9, min_mentions=3)

    # Verify results structure
    assert "total_sources" in results
    assert "key_sources_count" in results
    assert "threshold" in results
    assert results["threshold"] == 3
    assert "key_sources" in results

    print(f"✅ Total sources: {results['total_sources']}")
    print(f"✅ Key sources (≥3 mentions): {results['key_sources_count']}")


def test_export_summary(rag, mock_vectordb):
    """Test chapter summary export."""
    print("\n🧪 Testing Chapter Summary Export\n")

    # Mock the required data
    mock_results = create_mock_search_results(5, count=10)
    mock_vectordb.scroll.return_value = (mock_results, None)

    # Test markdown format
    markdown_summary = rag.export_chapter_summary(5, format="markdown")
    assert isinstance(markdown_summary, str)
    assert len(markdown_summary) > 0
    assert "# Chapter 5 Research Summary" in markdown_summary
    print("✅ Markdown export successful")

    # Test text format
    text_summary = rag.export_chapter_summary(5, format="text")
    assert isinstance(text_summary, str)
    assert len(text_summary) > 0
    print("✅ Text export successful")

    # Test json format
    json_summary = rag.export_chapter_summary(5, format="json")
    assert isinstance(json_summary, str)
    assert len(json_summary) > 0
    print("✅ JSON export successful")


def test_generate_bibliography(rag, mock_vectordb):
    """Test bibliography generation."""
    print("\n🧪 Testing Bibliography Generation\n")

    # Mock search to return results with proper structure
    mock_search_results = [
        {
            "text": "Test content",
            "metadata": {
                "title": "Test Book 1",
                "authors": "Doe, J.",
                "year": "2020",
                "publisher": "Test Publisher",
                "item_type": "book",
                "chapter_number": 4,
            },
        },
        {
            "text": "More content",
            "metadata": {
                "title": "Test Article",
                "authors": "Smith, A.",
                "year": "2021",
                "item_type": "article",
                "chapter_number": 4,
            },
        },
    ]

    with patch.object(rag, "search", return_value=mock_search_results):
        # Test APA format
        apa_bib = rag.generate_bibliography(chapter=4, style="apa")
        assert isinstance(apa_bib, list)
        if len(apa_bib) > 0:
            assert "citation" in apa_bib[0]
            assert "title" in apa_bib[0]
            print(f"✅ APA bibliography: {len(apa_bib)} entries")

        # Test MLA format
        mla_bib = rag.generate_bibliography(chapter=4, style="mla")
        assert isinstance(mla_bib, list)
        print(f"✅ MLA bibliography: {len(mla_bib)} entries")

        # Test Chicago format
        chicago_bib = rag.generate_bibliography(chapter=4, style="chicago")
        assert isinstance(chicago_bib, list)
        print(f"✅ Chicago bibliography: {len(chicago_bib)} entries")


def test_research_timeline(rag, mock_vectordb):
    """Test research timeline generation."""
    print("\n🧪 Testing Research Timeline\n")

    # Mock scroll results with different timestamps
    timeline_results = []
    months = ["2024-10-15", "2024-11-20", "2024-12-05"]
    for i, date in enumerate(months):
        for j in range(3):
            timeline_results.append(
                MagicMock(
                    payload={
                        "chapter_number": 5 + (i % 3),
                        "indexed_at": f"{date}T10:00:00Z",
                        "source_type": "zotero",
                        "title": f"Source {i}-{j}",
                    }
                )
            )

    mock_vectordb.scroll.return_value = (timeline_results, None)

    # Test timeline without chapter filter
    results = rag.get_research_timeline()
    assert "chapter" in results
    assert results["chapter"] is None
    assert "total_periods" in results
    assert "timeline" in results
    assert isinstance(results["timeline"], list)
    print(f"✅ Timeline spans {results['total_periods']} periods")

    # Test timeline with chapter filter
    results_ch5 = rag.get_research_timeline(chapter=5)
    assert results_ch5["chapter"] == 5
    print(f"✅ Chapter 5 timeline: {results_ch5['total_periods']} periods")


def test_recent_additions(rag, mock_vectordb):
    """Test recent additions tracking."""
    print("\n🧪 Testing Recent Additions\n")

    # Mock the get_index_stats method
    with patch.object(rag, "get_index_stats") as mock_stats:
        from datetime import datetime, timedelta

        recent_date = datetime.now() - timedelta(days=3)
        mock_stats.return_value = {
            "raw_timestamps": {
                "zotero": recent_date.isoformat(),
                "scrivener": recent_date.isoformat(),
            }
        }

        results = rag.get_recent_additions(days=7)

        # Verify results structure
        assert "cutoff_date" in results
        assert "sources" in results
        print(f"✅ Cutoff date: {results['cutoff_date']}")
        print(f"✅ Recent sources: {len(results['sources'])}")


def test_suggest_related_research(rag, mock_vectordb):
    """Test related research suggestions."""
    print("\n🧪 Testing Related Research Suggestions\n")

    # Mock search to return proper dict results
    chapter_search_results = [
        {"text": "Chapter 5 content about topic A", "metadata": {"chapter_number": 5}},
        {"text": "More chapter 5 content", "metadata": {"chapter_number": 5}},
    ]

    related_search_results = [
        {
            "text": "Related content from chapter 3",
            "score": 0.85,
            "metadata": {
                "chapter_number": 3,
                "chapter_title": "Chapter 3",
                "title": "Related Source",
            },
        },
        {
            "text": "Related content from chapter 7",
            "score": 0.80,
            "metadata": {
                "chapter_number": 7,
                "chapter_title": "Chapter 7",
                "title": "Another Source",
            },
        },
    ]

    # Mock search to return chapter content first, then related content
    with patch.object(rag, "search") as mock_search:
        mock_search.side_effect = [chapter_search_results, related_search_results]

        results = rag.suggest_related_research(5, limit=5)

        # Verify results structure
        assert "chapter" in results
        assert results["chapter"] == 5
        assert "suggestions_count" in results
        assert "chapters_with_suggestions" in results
        assert "suggestions" in results

        print(f"✅ Target chapter: {results['chapter']}")
        print(f"✅ Suggestions found: {results['suggestions_count']}")
        print(f"✅ From chapters: {results['chapters_with_suggestions']}")


def test_error_handling(rag, mock_vectordb):
    """Test error handling for invalid inputs."""
    print("\n🧪 Testing Error Handling\n")

    # Test with empty/None inputs where applicable
    mock_vectordb.scroll.return_value = ([], None)

    # Test compare_chapters with valid inputs but no data
    result = rag.compare_chapters(1, 2)
    # Should return a valid structure even with no data
    assert "chapter1" in result
    assert "chapter2" in result
    assert "comparison" in result
    print("✅ Handles chapters with no data")

    # Test export_chapter_summary with invalid format (should default to markdown)
    with patch.object(rag, "get_chapter_info", return_value={"indexed_chunks": 0}):
        with patch.object(
            rag, "analyze_source_diversity", return_value={"diversity_score": 0}
        ):
            with patch.object(
                rag, "identify_key_sources", return_value={"key_sources": []}
            ):
                result = rag.export_chapter_summary(5, format="invalid")
                # Should default to markdown
                assert isinstance(result, str)
                assert len(result) > 0
                print("✅ Handles invalid format gracefully")

    # Test with empty search results
    result = rag.find_cross_chapter_themes("nonexistent_theme")
    assert "keyword" in result
    assert result["keyword"] == "nonexistent_theme"
    print("✅ Handles theme with no results")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Testing New BookRAG Methods")
    print("=" * 60)

    try:
        test_cross_chapter_themes()
        test_compare_chapters()
        test_source_diversity()
        test_identify_key_sources()
        test_export_summary()
        test_generate_bibliography()
        test_research_timeline()
        test_recent_additions()
        test_suggest_related_research()
        test_error_handling()

        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
