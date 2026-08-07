from app.main import app


def test_documents_routes_are_exposed_at_expected_paths() -> None:
    paths = [route.path for route in app.routes if hasattr(route, "path")]

    assert "/api/v1/documents" in paths
    assert "/api/v1/documents/{document_id}" in paths
    assert "/api/v1/documents/documents" not in paths
