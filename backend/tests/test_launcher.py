from scripts.run_local import frontend_environment


def test_frontend_child_does_not_receive_backend_secrets():
    result = frontend_environment(
        {
            "PATH": "node",
            "API_BASE_URL": "http://127.0.0.1:8000",
            "NASA_API_KEY": "test-only",
            "SPACETRACK_USERNAME": "test-only",
            "SPACETRACK_PASSWORD": "test-only",
            "ADMIN_TOKEN": "test-only",
            "DATABASE_URL": "test-only",
            "POSTGRES_PASSWORD": "test-only",
        }
    )
    assert result == {"PATH": "node", "API_BASE_URL": "http://127.0.0.1:8000"}
