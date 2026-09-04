"""Ponto de entrada da aplicação."""

from __future__ import annotations

from investimentos.adapters.inbound.http.app import create_app

app = create_app()
