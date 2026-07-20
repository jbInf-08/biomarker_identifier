"""Unit tests for the NCBI PubMed E-utilities client.

Every network call is mocked; nothing here touches eutils.ncbi.nlm.nih.gov.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.services import pubmed_client


@pytest.fixture(autouse=True)
def _reset_throttle():
    """_LAST_CALL is module-global; reset it so tests do not affect each other."""
    pubmed_client._LAST_CALL = 0.0
    yield
    pubmed_client._LAST_CALL = 0.0


@pytest.fixture
def grounding_on():
    """Enable grounding and supply predictable NCBI identity settings."""
    with patch.object(pubmed_client, "settings") as s:
        s.ENABLE_PUBMED_GROUNDING = True
        s.NCBI_EMAIL = "researcher@example.org"
        s.NCBI_TOOL = "test_tool"
        s.NCBI_API_KEY = None
        yield s


def _esearch_response(idlist):
    r = MagicMock()
    r.raise_for_status.return_value = None
    r.json.return_value = {"esearchresult": {"idlist": idlist}}
    return r


def _efetch_response(xml_text):
    r = MagicMock()
    r.raise_for_status.return_value = None
    r.content = xml_text.encode("utf-8")
    return r


ARTICLE_XML = """<?xml version="1.0"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>12345</PMID>
      <Article>
        <ArticleTitle>BRCA1 in breast cancer</ArticleTitle>
        <Abstract><AbstractText>A study of BRCA1 variants.</AbstractText></Abstract>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>
"""


class TestThrottle:
    def test_sleeps_when_called_too_soon(self):
        pubmed_client._LAST_CALL = 100.0
        # monotonic returns a time only slightly after _LAST_CALL, so the
        # remaining interval must be slept off.
        with patch.object(pubmed_client.time, "monotonic", side_effect=[100.1, 100.4]):
            with patch.object(pubmed_client.time, "sleep") as sleep:
                pubmed_client._throttle()
        sleep.assert_called_once()
        assert sleep.call_args[0][0] == pytest.approx(pubmed_client._MIN_INTERVAL - 0.1)

    def test_does_not_sleep_when_interval_elapsed(self):
        pubmed_client._LAST_CALL = 0.0
        with patch.object(pubmed_client.time, "monotonic", side_effect=[50.0, 50.0]):
            with patch.object(pubmed_client.time, "sleep") as sleep:
                pubmed_client._throttle()
        sleep.assert_not_called()

    def test_updates_last_call(self):
        pubmed_client._LAST_CALL = 0.0
        with patch.object(pubmed_client.time, "monotonic", side_effect=[10.0, 11.0]):
            pubmed_client._throttle()
        assert pubmed_client._LAST_CALL == 11.0


class TestSearchPubmed:
    def test_returns_empty_when_grounding_disabled(self):
        with patch.object(pubmed_client, "settings") as s:
            s.ENABLE_PUBMED_GROUNDING = False
            with patch.object(pubmed_client.requests, "get") as get:
                assert pubmed_client.search_pubmed("BRCA1") == []
            get.assert_not_called()

    def test_returns_pmids_on_success(self, grounding_on):
        with patch.object(
            pubmed_client.requests, "get", return_value=_esearch_response(["1", "2"])
        ):
            assert pubmed_client.search_pubmed("BRCA1") == ["1", "2"]

    def test_sends_expected_query_params(self, grounding_on):
        with patch.object(
            pubmed_client.requests, "get", return_value=_esearch_response([])
        ) as get:
            pubmed_client.search_pubmed("TP53", retmax=7)
        params = get.call_args.kwargs["params"]
        assert params["db"] == "pubmed"
        assert params["term"] == "TP53"
        assert params["retmax"] == 7
        assert params["tool"] == "test_tool"
        assert params["email"] == "researcher@example.org"
        assert "api_key" not in params

    def test_includes_api_key_when_configured(self, grounding_on):
        grounding_on.NCBI_API_KEY = "secret-key"
        with patch.object(
            pubmed_client.requests, "get", return_value=_esearch_response([])
        ) as get:
            pubmed_client.search_pubmed("EGFR")
        assert get.call_args.kwargs["params"]["api_key"] == "secret-key"

    def test_returns_empty_on_request_exception(self, grounding_on):
        with patch.object(
            pubmed_client.requests, "get", side_effect=RuntimeError("network down")
        ):
            assert pubmed_client.search_pubmed("BRCA1") == []

    def test_returns_empty_when_payload_missing_idlist(self, grounding_on):
        r = MagicMock()
        r.raise_for_status.return_value = None
        r.json.return_value = {}
        with patch.object(pubmed_client.requests, "get", return_value=r):
            assert pubmed_client.search_pubmed("BRCA1") == []

    def test_returns_empty_when_idlist_is_null(self, grounding_on):
        r = MagicMock()
        r.raise_for_status.return_value = None
        r.json.return_value = {"esearchresult": {"idlist": None}}
        with patch.object(pubmed_client.requests, "get", return_value=r):
            assert pubmed_client.search_pubmed("BRCA1") == []


class TestFetchSummaries:
    def test_returns_empty_for_no_pmids(self, grounding_on):
        assert pubmed_client.fetch_summaries([]) == []

    def test_returns_empty_when_grounding_disabled(self):
        with patch.object(pubmed_client, "settings") as s:
            s.ENABLE_PUBMED_GROUNDING = False
            assert pubmed_client.fetch_summaries(["1"]) == []

    def test_parses_article_fields(self, grounding_on):
        with patch.object(
            pubmed_client.requests, "get", return_value=_efetch_response(ARTICLE_XML)
        ):
            out = pubmed_client.fetch_summaries(["12345"])
        assert len(out) == 1
        assert out[0]["pmid"] == "12345"
        assert out[0]["title"] == "BRCA1 in breast cancer"
        assert out[0]["text"] == "A study of BRCA1 variants."
        assert out[0]["source"] == "pubmed"

    def test_handles_article_missing_title_and_abstract(self, grounding_on):
        xml = """<PubmedArticleSet><PubmedArticle><MedlineCitation>
        <PMID>999</PMID></MedlineCitation></PubmedArticle></PubmedArticleSet>"""
        with patch.object(
            pubmed_client.requests, "get", return_value=_efetch_response(xml)
        ):
            out = pubmed_client.fetch_summaries(["999"])
        assert out == [{"pmid": "999", "title": "", "text": "", "source": "pubmed"}]

    def test_concatenates_nested_markup_in_title_and_abstract(self, grounding_on):
        xml = """<PubmedArticleSet><PubmedArticle><MedlineCitation>
        <PMID>7</PMID><Article>
        <ArticleTitle>Role of <i>TP53</i> here</ArticleTitle>
        <Abstract><AbstractText>Part <b>one</b> two</AbstractText></Abstract>
        </Article></MedlineCitation></PubmedArticle></PubmedArticleSet>"""
        with patch.object(
            pubmed_client.requests, "get", return_value=_efetch_response(xml)
        ):
            out = pubmed_client.fetch_summaries(["7"])
        assert out[0]["title"] == "Role of TP53 here"
        assert out[0]["text"] == "Part one two"

    def test_truncates_long_title_and_abstract(self, grounding_on):
        xml = (
            "<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>1</PMID>"
            "<Article><ArticleTitle>" + ("t" * 900) + "</ArticleTitle>"
            "<Abstract><AbstractText>" + ("a" * 2000) + "</AbstractText></Abstract>"
            "</Article></MedlineCitation></PubmedArticle></PubmedArticleSet>"
        )
        with patch.object(
            pubmed_client.requests, "get", return_value=_efetch_response(xml)
        ):
            out = pubmed_client.fetch_summaries(["1"])
        assert len(out[0]["title"]) == 500
        assert len(out[0]["text"]) == 1500

    def test_caps_request_at_ten_pmids(self, grounding_on):
        with patch.object(
            pubmed_client.requests, "get", return_value=_efetch_response(ARTICLE_XML)
        ) as get:
            pubmed_client.fetch_summaries([str(i) for i in range(25)])
        ids = get.call_args.kwargs["params"]["id"].split(",")
        assert len(ids) == 10
        assert ids[0] == "0" and ids[-1] == "9"

    def test_includes_api_key_when_configured(self, grounding_on):
        grounding_on.NCBI_API_KEY = "k1"
        with patch.object(
            pubmed_client.requests, "get", return_value=_efetch_response(ARTICLE_XML)
        ) as get:
            pubmed_client.fetch_summaries(["1"])
        assert get.call_args.kwargs["params"]["api_key"] == "k1"

    def test_returns_empty_on_request_exception(self, grounding_on):
        with patch.object(
            pubmed_client.requests, "get", side_effect=RuntimeError("boom")
        ):
            assert pubmed_client.fetch_summaries(["1"]) == []

    def test_returns_empty_on_malformed_xml(self, grounding_on):
        with patch.object(
            pubmed_client.requests, "get", return_value=_efetch_response("<not-xml")
        ):
            assert pubmed_client.fetch_summaries(["1"]) == []


class TestRetrievePubmedForGenes:
    def test_returns_empty_for_no_genes(self):
        assert pubmed_client.retrieve_pubmed_for_genes([]) == []

    def test_collects_and_tags_results_per_gene(self, grounding_on):
        with patch.object(pubmed_client, "search_pubmed", return_value=["1"]):
            with patch.object(
                pubmed_client,
                "fetch_summaries",
                return_value=[{"pmid": "1", "title": "t", "text": "x"}],
            ):
                out = pubmed_client.retrieve_pubmed_for_genes(["BRCA1"])
        assert len(out) == 1
        assert out[0]["genes"] == ["BRCA1"]

    def test_builds_cancer_scoped_query(self, grounding_on):
        with patch.object(pubmed_client, "search_pubmed", return_value=[]) as search:
            pubmed_client.retrieve_pubmed_for_genes(["BRCA1"], max_per_query=4)
        query = search.call_args[0][0]
        assert "BRCA1[Title/Abstract]" in query
        assert "cancer[Title/Abstract]" in query
        assert search.call_args.kwargs["retmax"] == 4

    def test_deduplicates_same_pmid_across_genes(self, grounding_on):
        with patch.object(pubmed_client, "search_pubmed", return_value=["1"]):
            with patch.object(
                pubmed_client,
                "fetch_summaries",
                return_value=[{"pmid": "1", "title": "t", "text": "x"}],
            ):
                out = pubmed_client.retrieve_pubmed_for_genes(["BRCA1", "TP53"])
        # Same PMID returned for both genes collapses to a single row.
        assert len(out) == 1

    def test_skips_rows_without_pmid(self, grounding_on):
        with patch.object(pubmed_client, "search_pubmed", return_value=["1"]):
            with patch.object(
                pubmed_client, "fetch_summaries", return_value=[{"title": "no pmid"}]
            ):
                assert pubmed_client.retrieve_pubmed_for_genes(["BRCA1"]) == []

    def test_limits_to_first_eight_genes(self, grounding_on):
        with patch.object(pubmed_client, "search_pubmed", return_value=[]) as search:
            pubmed_client.retrieve_pubmed_for_genes([f"G{i}" for i in range(20)])
        assert search.call_count == 8

    def test_caps_results_at_twelve(self, grounding_on):
        def _summaries(pmids):
            # 5 unique rows per gene, so 8 genes would yield 40 without the cap.
            base = _summaries.counter
            _summaries.counter += 5
            return [{"pmid": str(base + i), "title": "t"} for i in range(5)]

        _summaries.counter = 0
        with patch.object(pubmed_client, "search_pubmed", return_value=["x"]):
            with patch.object(pubmed_client, "fetch_summaries", side_effect=_summaries):
                out = pubmed_client.retrieve_pubmed_for_genes(
                    [f"G{i}" for i in range(8)]
                )
        assert len(out) == 12
