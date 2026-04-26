"""Integration tests for registration, login, and session-backed auth flows."""

from __future__ import annotations

import pytest


@pytest.mark.integration
def test_register_success(client, auth_databases):
    """Registering a new customer should create a user row and return a token."""
    response = client.post(
        "/auth/register",
        json={
            "name": "Alice Smith",
            "email": "alice@example.com",
            "phone": "07123456789",
            "address": "10 Downing St, London, SW1A 2AA",
            "password": "strongpass123",
        },
    )

    payload = response.get_json()
    assert response.status_code == 201
    assert payload["user"]["email"] == "alice@example.com"
    assert payload["token"]


@pytest.mark.integration
def test_duplicate_register_fails(client, auth_databases):
    """Duplicate email registration should return a conflict response."""
    payload = {
        "name": "Alice Smith",
        "email": "alice@example.com",
        "password": "strongpass123",
    }
    client.post("/auth/register", json=payload)
    response = client.post("/auth/register", json=payload)

    assert response.status_code == 409
    assert "already exists" in response.get_json()["error"]


@pytest.mark.integration
def test_login_success(client, auth_databases):
    """A registered customer should be able to log in successfully."""
    client.post(
        "/auth/register",
        json={"name": "Alice Smith", "email": "alice@example.com", "password": "strongpass123"},
    )

    response = client.post("/auth/login", json={"email": "alice@example.com", "password": "strongpass123"})

    assert response.status_code == 200
    assert response.get_json()["token"]


@pytest.mark.integration
def test_login_fail(client, auth_databases):
    """Incorrect credentials should return HTTP 401."""
    client.post(
        "/auth/register",
        json={"name": "Alice Smith", "email": "alice@example.com", "password": "strongpass123"},
    )

    response = client.post("/auth/login", json={"email": "alice@example.com", "password": "wrongpass"})

    assert response.status_code == 401
    assert "Incorrect email or password." == response.get_json()["error"]


@pytest.mark.integration
def test_session_persists(client, auth_databases):
    """A bearer token returned by registration should authenticate subsequent /me calls."""
    register = client.post(
        "/auth/register",
        json={"name": "Alice Smith", "email": "alice@example.com", "password": "strongpass123"},
    )
    token = register.get_json()["token"]

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.get_json()["user"]["email"] == "alice@example.com"
