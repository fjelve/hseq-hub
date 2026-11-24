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


def registrar(client, nombre, email, sector="mineria", pais="chile"):
    r = client.post(f"{P}/auth/registro", json={
        "empresa": nombre, "sector": sector, "pais": pais, "nombre": "Admin",
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


def test_plantillas_por_pais(client):
    cl = registrar(client, "Minera CL", "cl@example.com", "mineria", "chile")
    pe = registrar(client, "Minera PE", "pe@example.com", "mineria", "peru")
    cl_n = {p["norma"] for p in client.get(f"{P}/plantillas", headers=cl).json()}
    pe_n = {p["norma"] for p in client.get(f"{P}/plantillas", headers=pe).json()}
    assert "DS 132 (Chile)" in cl_n and "DS 024-2016-EM (Perú)" not in cl_n
    assert "DS 024-2016-EM (Perú)" in pe_n and "DS 132 (Chile)" not in pe_n
    assert "ISO 45001" in cl_n and "ISO 45001" in pe_n  # las genéricas aplican a ambos


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



def test_demo_incidentes_requisitos_dashboard(client):
    h = registrar(client, "Demo Min", "demo@example.com", "mineria", "peru")
    assert client.post(f"{P}/demo/cargar", headers=h).status_code == 201
    assert client.post(f"{P}/demo/cargar", headers=h).status_code == 409  # solo cuentas vacías
    d = client.get(f"{P}/dashboard", headers=h).json()
    s = d["seguridad"]
    assert s["horas_12m"] > 0 and s["indice_frecuencia"] is not None
    assert s["accidentes_ctp_12m"] == 2 and s["dias_perdidos_12m"] == 9
    assert s["dias_sin_accidente_ctp"] == 68
    assert len(d["tendencia_cumplimiento"]) == 4
    assert d["requisitos_vencidos"] >= 1 and d["requisitos_por_vencer"] >= 1
    reqs = client.get(f"{P}/requisitos", headers=h).json()
    assert {r["estado"] for r in reqs} >= {"vencido", "por_vencer", "vigente"}
    assert any(r["entidad"] == "OEFA" for r in reqs)
    amb = client.get(f"{P}/ambiental", headers=h).json()
    assert len(amb["agua_m3"]) == 12


def test_incidente_ctp_abre_investigacion(client):
    h = registrar(client, "Ind Inc", "inc@example.com", "industria", "chile")
    r = client.post(f"{P}/incidentes", headers=h, json={
        "tipo": "accidente_ctp", "severidad": "alta", "dias_perdidos": 4, "area": "Producción"})
    assert r.status_code == 201 and r.json()["hallazgo_id"]
    leve = client.post(f"{P}/incidentes", headers=h, json={"tipo": "casi_accidente", "severidad": "baja"})
    assert leve.json()["hallazgo_id"] is None
    assert client.post(f"{P}/incidentes", headers=h, json={
        "tipo": "casi_accidente", "dias_perdidos": 2}).status_code == 422
