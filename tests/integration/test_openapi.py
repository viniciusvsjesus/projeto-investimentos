"""T064 — O OpenAPI publicado cumpre o contrato escrito antes do código (RF-09).

O contrato em ``specs/001-cotacao-ticker/contracts/openapi.yaml`` foi escrito na
fase de plano, antes da implementação (Artigo I). Este teste verifica que a
implementação o cumpre.

A verificação é de **superconjunto**, não de igualdade: o FastAPI adiciona
elementos próprios (como o 422 automático de validação de parâmetros) que não
pertencem ao contrato acordado. O que o contrato promete tem que existir; o que
o framework acrescenta é livre.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

# O contrato vigente é o da Spec 002. O da Spec 001 fica no repositório como
# registro histórico daquela entrega, e não é mais comparado com a implementação.
CONTRATO = (
    Path(__file__).resolve().parents[2]
    / "specs"
    / "003-recurso-acoes-portugues"
    / "contracts"
    / "openapi.yaml"
)


@pytest.fixture(scope="module")
def contrato() -> dict:
    return yaml.safe_load(CONTRATO.read_text(encoding="utf-8"))


@pytest.fixture
def publicado(client) -> dict:
    resposta = client.get("/openapi.json")
    assert resposta.status_code == 200
    return resposta.json()


def test_todas_as_rotas_do_contrato_existem(contrato, publicado) -> None:
    for rota in contrato["paths"]:
        assert rota in publicado["paths"], f"rota ausente na implementação: {rota}"


def test_operation_ids_batem(contrato, publicado) -> None:
    for rota, metodos in contrato["paths"].items():
        for metodo, operacao in metodos.items():
            assert publicado["paths"][rota][metodo]["operationId"] == operacao["operationId"]


def test_todos_os_status_prometidos_estao_documentados(contrato, publicado) -> None:
    for rota, metodos in contrato["paths"].items():
        for metodo, operacao in metodos.items():
            prometidos = set(operacao["responses"])
            publicados = set(publicado["paths"][rota][metodo]["responses"])
            faltando = prometidos - publicados
            assert not faltando, f"{rota} {metodo}: faltam {faltando}"


def test_schema_de_cotacao_tem_todos_os_campos_do_contrato(contrato, publicado) -> None:
    esperados = set(contrato["components"]["schemas"]["CotacaoResponse"]["properties"])
    publicados = set(publicado["components"]["schemas"]["CotacaoResponse"]["properties"])
    assert esperados == publicados


def _tipos(schema: dict) -> set[str]:
    """Normaliza o tipo declarado, seja ele escalar ou união com null."""
    if "anyOf" in schema:
        return {sub.get("type", "?") for sub in schema["anyOf"]}
    tipo = schema.get("type", "?")
    return set(tipo) if isinstance(tipo, list) else {tipo}


def test_tipos_dos_campos_da_cotacao_batem(contrato, publicado) -> None:
    """Nome igual com tipo diferente é contrato quebrado que passa despercebido.

    Foi assim que se descobriu que `price` estava publicado como anulável: o
    serializador tinha retorno `float | None`, e um gerador de cliente
    produziria `Optional<Double>` para um campo que nunca vem nulo.
    """
    esperado = contrato["components"]["schemas"]["CotacaoResponse"]["properties"]
    publicado_props = publicado["components"]["schemas"]["CotacaoResponse"]["properties"]

    for campo, spec in esperado.items():
        assert _tipos(spec) == _tipos(publicado_props[campo]), (
            f"campo '{campo}': contrato diz {_tipos(spec)}, "
            f"implementação publica {_tipos(publicado_props[campo])}"
        )


def test_campos_obrigatorios_da_cotacao_batem(contrato, publicado) -> None:
    esperados = set(contrato["components"]["schemas"]["CotacaoResponse"]["required"])
    publicados = set(publicado["components"]["schemas"]["CotacaoResponse"]["required"])
    assert esperados == publicados


def test_schema_de_erro_tem_os_campos_do_contrato(contrato, publicado) -> None:
    esperados = set(contrato["components"]["schemas"]["ProblemDetail"]["properties"])
    publicados = set(publicado["components"]["schemas"]["ProblemDetail"]["properties"])
    assert esperados == publicados


def test_nenhum_caminho_tem_prefixo_de_versao(publicado) -> None:
    """FR-014 — versionar por mudança, não por caminho."""
    for rota in publicado["paths"]:
        assert not rota.startswith("/v"), f"{rota} tem prefixo de versão"
