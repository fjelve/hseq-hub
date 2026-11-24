"""Límite de intentos en memoria (ventana deslizante).

Limitación conocida: el estado vive en el proceso. Con varios workers cada uno
cuenta por separado, así que el límite efectivo es N veces mayor. Para escalar,
complementar con reglas de Cloudflare o mover el contador a Redis.
"""
import threading
import time
from collections import deque

from fastapi import HTTPException, Request

from app.config import get_settings


class Limiter:
    def __init__(self, maximo: int, ventana_s: int):
        self.maximo = maximo
        self.ventana = ventana_s
        self._hits: dict[str, deque] = {}
        self._lock = threading.Lock()

    def _purgar(self, key: str, ahora: float) -> deque:
        q = self._hits.setdefault(key, deque())
        while q and ahora - q[0] > self.ventana:
            q.popleft()
        return q

    def verificar(self, key: str) -> None:
        """Lanza 429 si ya se alcanzó el máximo en la ventana."""
        ahora = time.monotonic()
        with self._lock:
            q = self._purgar(key, ahora)
            if len(q) >= self.maximo:
                espera = int(self.ventana - (ahora - q[0])) + 1
                raise HTTPException(429, "Demasiados intentos. Inténtalo más tarde.",
                                    headers={"Retry-After": str(espera)})

    def registrar(self, key: str) -> None:
        ahora = time.monotonic()
        with self._lock:
            self._purgar(key, ahora).append(ahora)
            if len(self._hits) > 10_000:  # acota la memoria
                for k in [k for k, q in self._hits.items() if not q or ahora - q[-1] > self.ventana]:
                    del self._hits[k]

    def reiniciar(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)

    def limpiar(self) -> None:
        with self._lock:
            self._hits.clear()


_s = get_settings()
login_cuenta = Limiter(_s.LOGIN_MAX_FALLOS, _s.LOGIN_VENTANA_MIN * 60)  # clave: ip|correo
login_ip = Limiter(_s.LOGIN_MAX_FALLOS_IP, _s.LOGIN_VENTANA_MIN * 60)  # clave: ip
registro_ip = Limiter(_s.REGISTRO_MAX_POR_HORA, 3600)


def ip_cliente(request: Request) -> str:
    """IP del cliente. Las cabeceras de proxy solo se creen si TRUST_PROXY está activo."""
    if get_settings().TRUST_PROXY:
        for h in ("cf-connecting-ip", "x-real-ip"):
            v = request.headers.get(h)
            if v:
                return v.strip()
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()
    return request.client.host if request.client else "desconocida"
