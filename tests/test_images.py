import pytest
import math
from unittest.mock import patch, MagicMock

from scraper.images import GoogleImageSearcher, score_candidate


def test_score_candidate_exact_match():
    score = score_candidate(1200, 600)
    assert score == 0.0


def test_score_candidate_wrong_aspect_ratio():
    score = score_candidate(1000, 800)
    assert score > 1000


def test_score_candidate_close_dimensions_right_ratio():
    score = score_candidate(1180, 590)
    assert score < 100


def test_query_construction():
    searcher = GoogleImageSearcher("fake_key", "fake_cse", {})
    query = searcher.build_query(["NTR", "Devara", "Box Office"], "NTR's Devara Storms Box Office")
    assert isinstance(query, str)
    assert len(query) > 0
    assert "NTR" in query
    assert "telugu cinema" in query


def test_find_best_match():
    searcher = GoogleImageSearcher("fake_key", "fake_cse", {})
    results = [
        {"link": "http://img/1.jpg", "image": {"width": 1200, "height": 600}},
        {"link": "http://img/2.jpg", "image": {"width": 800, "height": 600}},
        {"link": "http://img/3.jpg", "image": {"width": 1200, "height": 500}},
    ]
    best = searcher.find_best_match(results)
    assert best == "http://img/1.jpg"


@patch("scraper.images.requests.get")
def test_search_api_call(mock_get):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "items": [
            {"link": "http://img/a.jpg", "image": {"width": 1200, "height": 600}},
        ]
    }
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    searcher = GoogleImageSearcher("fake_key", "fake_cse", {
        "google_cse": {"num_results": 10, "target_width": 1200, "target_height": 600}
    })
    results = searcher.search("NTR Devara")
    assert len(results) == 1
    assert results[0]["link"] == "http://img/a.jpg"
    mock_get.assert_called_once()
    _, kwargs = mock_get.call_args
    assert kwargs["params"]["q"] == "NTR Devara"


def test_get_image_for_story_falls_back():
    searcher = GoogleImageSearcher("fake_key", "fake_cse", {})
    result = searcher.get_image_for_story(["tag"], "Headline", fallback_url="http://fallback.jpg")
    # No API key means search returns no results, so fallback
    assert result == "http://fallback.jpg"
