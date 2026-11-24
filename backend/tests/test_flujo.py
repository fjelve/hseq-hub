import os
import tempfile
from datetime import date, timedelta

_db = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_db}"
os.environ["ENV"] = "development"
os.environ["AUTO_CREATE_TABLES"] = "1"
os.environ["REGISTRO_MAX_POR_HORA"] = "1000"  # las pruebas crean muchas empresas desde la misma IP

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


def test_sostenibilidad_emisiones_metas_gri(client):
    h = registrar(client, "Sos Min", "sos@example.com", "mineria", "chile")
    # sin datos: no hay emisiones ni valores reportables
    assert client.get(f"{P}/emisiones", headers=h).json()["total_12m"]["total"] == 0
    # 1000 L diésel (alcance 1) y 10.000 kWh (alcance 2), factores referenciales Chile
    for tipo, v in [("combustible_l", 1000), ("energia_kwh", 10000)]:
        assert client.put(f"{P}/ambiental", headers=h, json={"periodo": "2026-01", "tipo": tipo, "valor": v}).status_code == 200
    e = client.get(f"{P}/emisiones", headers=h).json()
    assert e["total_12m"]["alcance1"] == 2.68 and e["total_12m"]["alcance2"] == 3.5
    assert all(f["referencial"] for f in e["factores"])
    # factor propio reemplaza al referencial
    assert client.put(f"{P}/factores", headers=h, json={"clave": "energia_kwh", "valor": 0.2, "fuente": "Factor oficial 2025"}).status_code == 200
    e = client.get(f"{P}/emisiones", headers=h).json()
    assert e["total_12m"]["alcance2"] == 2.0
    assert not next(f for f in e["factores"] if f["clave"] == "energia_kwh")["referencial"]
    # metas
    assert client.post(f"{P}/metas", headers=h, json={"nombre": "Meta mala", "indicador": "agua_m3", "anio_base": 2030,
                       "valor_base": 100, "anio_meta": 2025, "reduccion_pct": 10}).status_code == 422
    m = client.post(f"{P}/metas", headers=h, json={"nombre": "Menos emisiones", "indicador": "emisiones_tco2e",
                    "anio_base": 2025, "valor_base": 10, "anio_meta": 2030, "reduccion_pct": 50}).json()
    assert m["valor_objetivo"] == 5 and m["valor_actual"] == 4.68 and m["estado"] == "cumplida"
    # social y validación
    client.put(f"{P}/social", headers=h, json={"periodo": "2026-01", "tipo": "empleados_total", "valor": 100})
    assert client.put(f"{P}/social", headers=h, json={"periodo": "2026-01", "tipo": "mujeres_empleadas", "valor": 150}).status_code == 422
    client.put(f"{P}/social", headers=h, json={"periodo": "2026-01", "tipo": "mujeres_empleadas", "valor": 20})
    gri = {(g["codigo"], g["indicador"]): g for g in client.get(f"{P}/reporte/gri", headers=h).json()}
    assert gri[("GRI 405-1", "Mujeres en la dotación")]["valor"] == 20.0
    assert gri[("GRI 303-5", "Consumo de agua")]["reportable"] is False
    # aislamiento: otra empresa no ve estas metas
    h2 = registrar(client, "Sos Otra", "sos2@example.com", "industria", "peru")
    assert client.get(f"{P}/metas", headers=h2).json() == []


def test_plantillas_sostenibilidad_por_pais(client):
    cl = registrar(client, "Sos CL", "soscl@example.com", "mineria", "chile")
    pe = registrar(client, "Sos PE", "sospe@example.com", "industria", "peru")
    n_cl = {p["clave"] for p in client.get(f"{P}/plantillas", headers=cl).json()}
    n_pe = {p["clave"] for p in client.get(f"{P}/plantillas", params={"sector": "industria"}, headers=pe).json()}
    assert {"sos-gistm", "cl-sos-clima-rep", "sos-ghg-14064"} <= n_cl and "pe-sos-clima-residuos" not in n_cl
    assert "sos-gistm" not in n_pe and {"pe-sos-clima-residuos", "sos-niif-s1-s2"} <= n_pe


# ---------------------------------------------------------------- seguridad y trazabilidad
def test_login_limita_intentos_por_cuenta(client):
    from app import ratelimit
    ratelimit.login_cuenta.limpiar(); ratelimit.login_ip.limpiar()
    registrar(client, "Lim Ind", "lim@example.com", "industria")
    for _ in range(5):
        assert client.post(f"{P}/auth/login", data={"username": "lim@example.com", "password": "incorrecta123"}).status_code == 401
    r = client.post(f"{P}/auth/login", data={"username": "lim@example.com", "password": "ClaveSegura123"})
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0  # bloquea aun con la clave correcta
    # otro correo desde la misma IP no queda bloqueado
    registrar(client, "Lim Ind 2", "lim2@example.com", "industria")
    assert client.post(f"{P}/auth/login", data={"username": "lim2@example.com", "password": "ClaveSegura123"}).status_code == 200
    ratelimit.login_cuenta.limpiar(); ratelimit.login_ip.limpiar()


def test_login_correcto_reinicia_contador(client):
    from app import ratelimit
    ratelimit.login_cuenta.limpiar(); ratelimit.login_ip.limpiar()
    registrar(client, "Lim Ind 3", "lim3@example.com", "industria")
    for _ in range(4):
        client.post(f"{P}/auth/login", data={"username": "lim3@example.com", "password": "mala-clave-123"})
    assert client.post(f"{P}/auth/login", data={"username": "lim3@example.com", "password": "ClaveSegura123"}).status_code == 200
    for _ in range(4):  # el contador volvió a cero
        assert client.post(f"{P}/auth/login", data={"username": "lim3@example.com", "password": "mala-clave-123"}).status_code == 401
    ratelimit.login_cuenta.limpiar(); ratelimit.login_ip.limpiar()


def test_registro_limitado_por_ip(client):
    from app import ratelimit
    anterior = ratelimit.registro_ip.maximo
    ratelimit.registro_ip.limpiar(); ratelimit.registro_ip.maximo = 2
    try:
        codigos = [client.post(f"{P}/auth/registro", json={
            "empresa": "Spam SA", "sector": "industria", "pais": "chile", "nombre": "Xy",
            "email": f"spam{i}@example.com", "password": "ClaveSegura123"}).status_code for i in range(3)]
        assert codigos == [201, 201, 429]
    finally:
        ratelimit.registro_ip.maximo = anterior
        ratelimit.registro_ip.limpiar()


def test_cabeceras_de_proxy_se_ignoran_sin_trust_proxy(client):
    from app import ratelimit
    ratelimit.login_cuenta.limpiar(); ratelimit.login_ip.limpiar()
    registrar(client, "Lim Ind 4", "lim4@example.com", "industria")
    for i in range(5):  # el atacante cambia X-Forwarded-For en cada intento: no evade el límite
        client.post(f"{P}/auth/login", headers={"X-Forwarded-For": f"10.0.0.{i}"},
                    data={"username": "lim4@example.com", "password": "mala-clave-123"})
    r = client.post(f"{P}/auth/login", headers={"X-Forwarded-For": "10.9.9.9"},
                    data={"username": "lim4@example.com", "password": "ClaveSegura123"})
    assert r.status_code == 429
    ratelimit.login_cuenta.limpiar(); ratelimit.login_ip.limpiar()


def test_bitacora_encadenada_y_detecta_alteraciones(client):
    from sqlalchemy import text
    h = registrar(client, "Bit Min", "bit@example.com", "mineria")
    hid = client.post(f"{P}/hallazgos", headers=h, json={"titulo": "Cable pelado en tablero"}).json()["id"]
    client.patch(f"{P}/hallazgos/{hid}", headers=h, json={"causa_raiz": "Falta de mantenimiento"})
    client.post(f"{P}/hallazgos/{hid}/acciones", headers=h, json={"descripcion": "Reemplazar cable"})
    entradas = client.get(f"{P}/bitacora", headers=h).json()
    assert [e["accion"] for e in reversed(entradas)] == [
        "empresa.registro", "hallazgo.crear", "hallazgo.actualizar", "hallazgo.accion_agregada"]
    v = client.get(f"{P}/bitacora/verificar", headers=h).json()
    assert v["valida"] and v["entradas"] == 4 and len(v["ultimo_hash"]) == 64

    # Alterar el contenido de una entrada intermedia (esta base de prueba no tiene los disparadores)
    db = SessionLocal()
    try:
        db.execute(text("UPDATE bitacora SET datos='{\"codigo\":\"FALSO\"}' WHERE accion='hallazgo.crear' "
                        "AND empresa_id=(SELECT empresa_id FROM usuarios WHERE email='bit@example.com')"))
        db.commit()
    finally:
        db.close()
    v = client.get(f"{P}/bitacora/verificar", headers=h).json()
    assert v["valida"] is False and v["primer_error"]["seq"] == 2


def test_bitacora_aislada_y_solo_para_admin_o_auditor(client):
    h1 = registrar(client, "Bit A", "bita@example.com", "industria")
    h2 = registrar(client, "Bit B", "bitb@example.com", "industria")
    client.post(f"{P}/hallazgos", headers=h1, json={"titulo": "Solo de A"})
    assert all("Solo de A" not in e["datos"] for e in client.get(f"{P}/bitacora", headers=h2).json())
    client.post(f"{P}/usuarios", headers=h1, json={"nombre": "Op", "email": "opbita@example.com",
                                                    "password": "ClaveSegura123", "rol": "responsable"})
    t = client.post(f"{P}/auth/login", data={"username": "opbita@example.com", "password": "ClaveSegura123"}).json()["access_token"]
    assert client.get(f"{P}/bitacora", headers={"Authorization": f"Bearer {t}"}).status_code == 403


def test_migracion_crea_esquema_y_bitacora_es_inmutable(tmp_path):
    import sqlite3
    import subprocess
    import sys
    db = tmp_path / "migrada.db"
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db.as_posix()}"}
    env.pop("AUTO_CREATE_TABLES", None)
    r = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], env=env,
                       cwd=os.path.dirname(os.path.dirname(__file__)), capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    con = sqlite3.connect(db)
    tablas = {n for (n,) in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"empresas", "hallazgos", "bitacora", "alembic_version"} <= tablas
    con.execute("INSERT INTO empresas (nombre, sector, pais) VALUES ('X','mineria','chile')")
    con.execute("INSERT INTO bitacora (empresa_id, seq, ts, actor, accion, entidad, datos, hash_previo, hash_actual) "
                "VALUES (1, 1, 't', 'a', 'x', 'e', '{}', '0', '1')")
    con.commit()
    for sql in ("UPDATE bitacora SET actor='otro'", "DELETE FROM bitacora"):
        try:
            con.execute(sql)
            assert False, f"debió fallar: {sql}"
        except sqlite3.DatabaseError as e:
            assert "solo escritura" in str(e)
    con.close()
