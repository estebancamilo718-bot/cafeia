"""Pruebas de los dos servidores MCP y del agente /analizar.

Usan un predictor falso y un Open-Meteo simulado: no cargan el modelo real ni
salen a internet, así que corren igual en CI.
"""

from __future__ import annotations

import base64
from contextlib import asynccontextmanager
from io import BytesIO

import anyio
import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient
from mcp import Client
from PIL import Image

import backend.main as api
from backend import clima
from backend.mcp_servidores import crear_servidor_clasificador, crear_servidor_clima
from test_api_contract import FakePredictor, OutsideDomainPredictor

GEOCODING_IBAGUE = {
    "results": [
        {
            "name": "Ibagué",
            "admin1": "Tolima",
            "country": "Colombia",
            "latitude": 4.43573,
            "longitude": -75.20289,
            "elevation": 1047.0,
        }
    ]
}
CLIMA_ACTUAL = {
    "current": {
        "time": "2026-11-16T22:15",
        "temperature_2m": 21.4,
        "relative_humidity_2m": 91,
        "precipitation": 0.0,
    }
}
PRONOSTICO = {
    "daily": {
        "time": ["2026-11-16", "2026-11-17", "2026-11-18"],
        "temperature_2m_max": [28.1, 26.4, 26.5],
        "temperature_2m_min": [19.4, 20.0, 17.8],
        "precipitation_sum": [3.4, 4.3, 5.7],
        "precipitation_probability_max": [99, 94, 100],
        "relative_humidity_2m_mean": [76, 84, 88],
    }
}


def open_meteo_simulado(request: httpx.Request) -> httpx.Response:
    if request.url.host == "geocoding-api.open-meteo.com":
        if request.url.params["name"] == "Ibagué":
            return httpx.Response(200, json=GEOCODING_IBAGUE)
        return httpx.Response(200, json={})
    if "current" in request.url.params:
        return httpx.Response(200, json=CLIMA_ACTUAL)
    return httpx.Response(200, json=PRONOSTICO)


def open_meteo_caido(request: httpx.Request) -> httpx.Response:
    return httpx.Response(503)


def image_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (32, 24), (72, 112, 65)).save(output, format="JPEG")
    return output.getvalue()


@pytest.fixture(autouse=True)
def limpiar_cache_de_ciudades():
    clima._ubicaciones.clear()
    yield
    clima._ubicaciones.clear()


def cliente_agente(monkeypatch: pytest.MonkeyPatch, predictor, manejador_open_meteo):
    @asynccontextmanager
    async def lifespan_simulado(app):
        app.state.predictor = predictor
        transporte = httpx.MockTransport(manejador_open_meteo)
        async with httpx.AsyncClient(transport=transporte) as cliente_http:
            async with api.iniciar_mcp(app, cliente_http):
                yield

    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "testserver")
    monkeypatch.setattr(api.app.router, "lifespan_context", lifespan_simulado)
    return TestClient(api.app, raise_server_exceptions=False)


def analizar(client: TestClient, ciudad: str = "Ibagué"):
    return client.post(
        "/analizar",
        data={"ciudad": ciudad},
        files={"file": ("hoja.jpg", image_bytes(), "image/jpeg")},
    )


def test_agente_usa_los_dos_sensores_mcp(monkeypatch: pytest.MonkeyPatch) -> None:
    with cliente_agente(monkeypatch, FakePredictor(), open_meteo_simulado) as client:
        response = analizar(client)

    assert response.status_code == 200
    payload = response.json()
    assert payload["prediccion"]["category"] == "coffee___healthy"
    assert payload["clima_mensaje"] is None
    assert payload["clima"]["actual"]["ubicacion"]["departamento"] == "Tolima"
    assert payload["clima"]["actual"]["humedad_relativa_pct"] == 91
    assert len(payload["clima"]["pronostico"]["dias"]) == 3
    assert [(paso["herramienta"], paso["estado"]) for paso in payload["pasos"]] == [
        ("clasificar_hoja", "ok"),
        ("clima_actual", "ok"),
        ("pronostico", "ok"),
    ]


def test_agente_no_consulta_el_clima_si_la_imagen_es_rechazada(monkeypatch: pytest.MonkeyPatch) -> None:
    llamadas: list[httpx.Request] = []

    def registrar(request: httpx.Request) -> httpx.Response:
        llamadas.append(request)
        return open_meteo_simulado(request)

    with cliente_agente(monkeypatch, OutsideDomainPredictor(), registrar) as client:
        response = analizar(client)

    assert response.status_code == 200
    payload = response.json()
    assert payload["prediccion"]["status"] == "outside_domain"
    assert payload["prediccion"]["scores"] == []
    assert payload["clima"] is None
    assert payload["clima_mensaje"] == api.CLIMA_OMITIDO_MESSAGE
    assert payload["pasos"][1]["estado"] == "omitida"
    assert llamadas == []


def test_falla_del_clima_no_bloquea_el_diagnostico(monkeypatch: pytest.MonkeyPatch) -> None:
    with cliente_agente(monkeypatch, FakePredictor(), open_meteo_caido) as client:
        response = analizar(client)

    assert response.status_code == 200
    payload = response.json()
    assert payload["prediccion"]["status"] == "classified"
    assert payload["clima"] is None
    assert "Open-Meteo" in payload["clima_mensaje"]
    assert [(paso["herramienta"], paso["estado"]) for paso in payload["pasos"]][1:] == [
        ("clima_actual", "error"),
        ("pronostico", "omitida"),
    ]


def test_ciudad_desconocida_se_explica_al_usuario(monkeypatch: pytest.MonkeyPatch) -> None:
    with cliente_agente(monkeypatch, FakePredictor(), open_meteo_simulado) as client:
        response = analizar(client, ciudad="Ciudad Inventada")

    assert response.status_code == 200
    assert response.json()["clima_mensaje"] == "No encontramos «Ciudad Inventada» entre las ciudades de Colombia."


def test_analizar_valida_la_fotografia_igual_que_predict(monkeypatch: pytest.MonkeyPatch) -> None:
    with cliente_agente(monkeypatch, FakePredictor(), open_meteo_simulado) as client:
        response = client.post(
            "/analizar",
            files={"file": ("hoja.gif", b"GIF89a", "image/gif")},
        )

    assert response.status_code == 415


def test_servidores_publicados_por_http_responden_a_un_cliente_mcp(monkeypatch: pytest.MonkeyPatch) -> None:
    with cliente_agente(monkeypatch, FakePredictor(), open_meteo_simulado) as client:
        for ruta, herramientas in (
            ("/clasificador/mcp", ["clasificar_hoja", "estado_modelo"]),
            ("/clima/mcp", ["clima_actual", "pronostico"]),
        ):
            response = client.post(
                ruta,
                headers={"Accept": "application/json, text/event-stream"},
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            )
            assert response.status_code == 200, response.text
            nombres = sorted(tool["name"] for tool in response.json()["result"]["tools"])
            assert nombres == herramientas


def test_host_no_autorizado_es_rechazado(monkeypatch: pytest.MonkeyPatch) -> None:
    with cliente_agente(monkeypatch, FakePredictor(), open_meteo_simulado) as client:
        response = client.post(
            "/clima/mcp",
            headers={"Accept": "application/json, text/event-stream", "Host": "sitio-ajeno.example"},
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        )

    assert response.status_code == 421


def test_clasificador_mcp_rechaza_base64_invalido_y_conserva_el_contrato() -> None:
    servidor = crear_servidor_clasificador(FakePredictor)

    async def probar():
        async with Client(servidor, mode="legacy") as cliente:
            invalido = await cliente.call_tool(
                "clasificar_hoja", {"imagen_base64": "no es base64", "formato": "jpeg"}
            )
            valido = await cliente.call_tool(
                "clasificar_hoja",
                {"imagen_base64": base64.b64encode(image_bytes()).decode(), "formato": "jpeg"},
            )
            formato_falso = await cliente.call_tool(
                "clasificar_hoja",
                {"imagen_base64": base64.b64encode(image_bytes()).decode(), "formato": "png"},
            )
        return invalido, valido, formato_falso

    invalido, valido, formato_falso = anyio.run(probar)
    assert invalido.is_error
    assert not valido.is_error
    api.PredictionResponse.model_validate(valido.structured_content)
    assert formato_falso.is_error
    assert "PNG" in formato_falso.content[0].text


def test_clima_mcp_rechaza_dias_fuera_de_rango() -> None:
    async def probar():
        transporte = httpx.MockTransport(open_meteo_simulado)
        async with httpx.AsyncClient(transport=transporte) as cliente_http:
            servidor = crear_servidor_clima(cliente_http)
            async with Client(servidor, mode="legacy") as cliente:
                return await cliente.call_tool("pronostico", {"ciudad": "Ibagué", "dias": 30})

    resultado = anyio.run(probar)
    assert resultado.is_error


def test_reintenta_una_vez_si_falla_la_conexion(monkeypatch: pytest.MonkeyPatch) -> None:
    intentos = {"geocodificacion": 0}

    def falla_la_primera_vez(request: httpx.Request) -> httpx.Response:
        if request.url.host == "geocoding-api.open-meteo.com":
            intentos["geocodificacion"] += 1
            if intentos["geocodificacion"] == 1:
                raise httpx.ConnectError("getaddrinfo failed", request=request)
        return open_meteo_simulado(request)

    with cliente_agente(monkeypatch, FakePredictor(), falla_la_primera_vez) as client:
        response = analizar(client)

    assert response.status_code == 200
    assert response.json()["clima"] is not None
    assert intentos["geocodificacion"] == 2
