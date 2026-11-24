import os
import tempfile
from datetime import date, timedelta

_db = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_db}"
os.environ["ENV"] = "development"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.services.alertas import revisar_vencimientos  # noqa: E402

P = "/api/v1"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def registrar(client, nombre, email, sector="mineria"):
    r = client.post(f"{P}/auth/registro", json={
        "empresa": nombre, "sector": sector, "nombre": "Admin",
        "email": email, "password": "ClaveSegura123"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_auth_requerida(client):
    assert client.get(f"{P}/hallazgos").status_code == 401


def test_flujo_auditoria_a_capa(client):
    h = registrar(client, "Minera A", "a@minera.example.com")
    plantillas = client.get(f"{P}/plantillas", params={"sector": "mineria"}, headers=h).json()
    assert plantillas and all(p["sector"] in ("mineria", "todos") for p in plantillas)
    pl = plantillas[0]

    aud = client.post(f"{P}/auditorias", json={"plantilla_id": pl["id"], "area": "Mina Rajo"},
                      headers=h).json()
    # No se puede cerrar incompleta
    assert client.post(f"{P}/auditorias/{aud['id']}/cerrar", headers=h).status_code == 409

    for n, item in enumerate(pl["items"]):
        res = "no_cumple" if n < 2 else "cumple"
        r = client.put(f"{P}/auditorias/{aud['id']}/respuestas", headers=h,
                       json={"item_id": item["id"], "resultado": res, "observacion": "obs"})
        assert r.status_code == 200

    cerrada = client.post(f"{P}/auditorias/{aud['id']}/cerrar", headers=h).json()
    total = len(pl["items"])
    assert cerrada["estado"] == "cerrada"
    assert cerrada["puntaje"] == round(100 * (total - 2) / total)
    hs = client.get(f"{P}/hallazgos", headers=h).json()
    assert len(hs) == 2 and all(x["origen"] == "auditoria" for x in hs)
    assert hs[0]["fecha_compromiso"]  # plazo automático por severidad

    # Ciclo CAPA
    hid = hs[0]["id"]
    assert client.post(f"{P}/hallazgos/{hid}/cerrar", headers=h,
                       json={"verificacion_eficacia": "Sin recurrencia en 30 días"}).status_code == 409
    client.patch(f"{P}/hallazgos/{hid}", headers=h,
                 json={"causa_raiz": "Falta de verificación previa", "metodo_causa": "5_porques"})
    a = client.post(f"{P}/hallazgos/{hid}/acciones", headers=h,
                    json={"descripcion": "Capacitar y verificar candados"}).json()
    client.post(f"{P}/hallazgos/{hid}/acciones/{a['id']}/completar", headers=h,
                json={"evidencia": "Acta 123"})
    assert client.get(f"{P}/hallazgos/{hid}", headers=h).json()["estado"] == "en_verificacion"
    r = client.post(f"{P}/hallazgos/{hid}/cerrar", headers=h,
                    json={"verificacion_eficacia": "Sin recurrencia en 30 días"})
    assert r.status_code == 200 and r.json()["estado"] == "cerrado"

    d = client.get(f"{P}/dashboard", headers=h).json()
    assert d["hallazgos_abiertos"] == 1 and d["cumplimiento_promedio"] == cerrada["puntaje"]


def test_aislamiento_entre_empresas(client):
    h1 = registrar(client, "Industria 1", "i1@ind.example.com", "industria")
    h2 = registrar(client, "Industria 2", "i2@ind.example.com", "industria")
    hid = client.post(f"{P}/hallazgos", headers=h1, json={"titulo": "Fuga de aceite"}).json()["id"]
    assert client.get(f"{P}/hallazgos/{hid}", headers=h2).status_code == 404
    assert client.get(f"{P}/hallazgos", headers=h2).json() == []
    assert client.patch(f"{P}/hallazgos/{hid}", headers=h2, json={"titulo": "x"}).status_code == 404


def test_rol_responsable_no_escribe(client):
    h = registrar(client, "Ind 3", "i3@ind.example.com", "industria")
    client.post(f"{P}/usuarios", headers=h, json={
        "nombre": "Op", "email": "op@ind.example.com", "password": "ClaveSegura123", "rol": "responsable"})
    t = client.post(f"{P}/auth/login", data={"username": "op@ind.example.com",
                                              "password": "ClaveSegura123"}).json()["access_token"]
    r = client.post(f"{P}/hallazgos", headers={"Authorization": f"Bearer {t}"},
                    json={"titulo": "No debería"})
    assert r.status_code == 403


def test_alertas_vencidos(client):
    h = registrar(client, "Ind 4", "i4@ind.example.com", "industria")
    ayer = (date.today() - timedelta(days=1)).isoformat()
    client.post(f"{P}/hallazgos", headers=h, json={"titulo": "Vencido", "fecha_compromiso": ayer})
    db = SessionLocal()
    try:
        al = revisar_vencimientos(db)
        assert any(a["tipo"] == "VENCIDO" for a in al)
        assert not any(a["tipo"] == "VENCIDO" for a in revisar_vencimientos(db))  # no se repite
    finally:
        db.close()
    assert client.get(f"{P}/hallazgos", params={"solo_vencidos": True}, headers=h).json()[0]["vencido"]

