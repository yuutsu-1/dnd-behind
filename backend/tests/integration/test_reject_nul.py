"""A NUL character (\\x00) can't be stored in Postgres text: any request carrying one
(query string, path or JSON body) must be a 422, never a DBAPIError (500)."""
import json

import pytest

from tests.integration.conftest import auth_headers, seed_user


@pytest.mark.parametrize("url", [
    "/api/compendium/items?search=a%00b",
    "/api/compendium/spells?search=a%00b",
    "/api/compendium/damage-types?search=a%00b",
    "/api/compendium/damage-types/fire%00",
])
async def test_nul_in_query_or_path_is_422(api_client, url):
    response = await api_client.get(url)
    assert response.status_code == 422
    assert "NUL" in response.json()["detail"]


async def test_nul_in_json_body_is_422_and_writes_nothing(api_client, db_session):
    user = await seed_user(db_session)
    await db_session.commit()
    body = json.dumps({"code": "nul_test", "name": "Bad\u0000Name"})
    response = await api_client.post(
        "/api/compendium/damage-types",
        content=body,
        headers={**auth_headers(user), "Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert (await api_client.get("/api/compendium/damage-types/nul_test", headers=auth_headers(user))).status_code == 404


async def test_escaped_backslash_followed_by_u0000_text_is_allowed(api_client, db_session):
    """A literal backslash followed by the text `u0000` is not a NUL character."""
    user = await seed_user(db_session)
    await db_session.commit()
    response = await api_client.post(
        "/api/compendium/damage-types",
        json={"code": "backslash_test", "name": "Back", "description": "path\\u0000text"},
        headers=auth_headers(user),
    )
    assert response.status_code == 201, response.text
    assert response.json()["description"] == "path\\u0000text"


async def test_regular_search_still_works(api_client):
    response = await api_client.get("/api/compendium/damage-types", params={"search": "fir"})
    assert [row["code"] for row in response.json()] == ["fire"]
