from canine_evidence.deduplication import deduplicate


def test_first_pmid_wins_and_idempotent(pubmed_fixture):
    articles = pubmed_fixture[3]
    # Fault injection on captured data; these mutations are never stored as research.
    later = articles[0].model_copy(update={"title": None})
    result = deduplicate([articles[0], later, articles[1], articles[0]])
    assert result == articles[:2]
    assert result[0] is articles[0]
    assert deduplicate(result) == result


def test_doi_collision_keeps_both(pubmed_fixture, caplog):
    articles = pubmed_fixture[3]
    first = articles[1]
    second = articles[2].model_copy(update={"doi": first.doi})
    assert deduplicate([first, second]) == [first, second]
    assert "DOI collision" in caplog.text


def test_missing_pmid_defense(pubmed_fixture, caplog):
    invalid = pubmed_fixture[3][0].model_copy(update={"pmid": None})
    assert deduplicate([invalid]) == []
    assert "without PMID" in caplog.text


def test_null_doi_does_not_collide(pubmed_fixture, caplog):
    articles = [a.model_copy(update={"doi": None}) for a in pubmed_fixture[3]]
    assert deduplicate(articles) == articles
    assert "DOI collision" not in caplog.text
