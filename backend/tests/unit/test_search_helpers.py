import pytest

from app.services.search import escape_like


@pytest.mark.parametrize("term,expected", [
    ("fire", "fire"),
    ("a_b", "a\\_b"),
    ("50%", "50\\%"),
    ("back\\slash", "back\\\\slash"),
])
def test_escape_like_makes_wildcards_literal(term, expected):
    assert escape_like(term) == expected


def test_no_module_keeps_a_private_copy():
    import app.api.reference as reference_api
    import app.services.items as items_service
    import app.services.spells as spells_service

    for module in (reference_api, items_service, spells_service):
        assert not hasattr(module, "_escape_like")
