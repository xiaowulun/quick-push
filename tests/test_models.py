from web.backend.models import SearchResult


def test_search_result_list_fields_use_default_factory():
    fields = SearchResult.model_fields
    assert fields["keywords"].default_factory is list
    assert fields["tech_stack"].default_factory is list
    assert fields["use_cases"].default_factory is list
