from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

Severidad = Literal["baja", "media", "alta", "critica"]
Estado = Literal["abierto", "en_proceso", "en_verificacion", "cerrado"]


class RegistroIn(BaseModel):
    empresa: str = Field(min_length=2, max_length=200)
    sector: Literal["mineria", "industria"]
    pais: Literal["chile", "peru"]
    nombre: str = Field(min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(min_length=10, max_length=72)


class UsuarioIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(min_length=10, max_length=72)
    rol: Literal["admin", "auditor", "responsable"] = "responsable"


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str
    email: str
    rol: str


class AccionIn(BaseModel):
    tipo: Literal["inmediata", "correctiva", "preventiva"] = "correctiva"
    descripcion: str = Field(min_length=3)
    responsable_id: Optional[int] = None
    fecha_compromiso: Optional[date] = None


class AccionOut(AccionIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    completada: bool
    fecha_completada: Optional[date] = None
    evidencia: str = ""


class AccionCompletar(BaseModel):
    evidencia: str = Field(min_length=3)


class HallazgoIn(BaseModel):
    titulo: str = Field(min_length=3, max_length=250)
    descripcion: str = ""
    origen: Literal["auditoria", "inspeccion", "incidente", "otro"] = "otro"
    norma: str = ""
    area: str = ""
    severidad: Severidad = "media"
    responsable_id: Optional[int] = None
    fecha_compromiso: Optional[date] = None


class HallazgoUpdate(BaseModel):
    titulo: Optional[str] = None
    descripcion: Optional[str] = None
    severidad: Optional[Severidad] = None
    area: Optional[str] = None
    causa_raiz: Optional[str] = None
    metodo_causa: Optional[Literal["5_porques", "ishikawa", "otro"]] = None
    responsable_id: Optional[int] = None
    fecha_compromiso: Optional[date] = None


class CerrarIn(BaseModel):
    verificacion_eficacia: str = Field(min_length=10)


class HallazgoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    codigo: str
    titulo: str
    descripcion: str
    origen: str
    norma: str
    area: str
    severidad: str
    estado: str
    causa_raiz: str
    metodo_causa: str
    responsable_id: Optional[int]
    fecha_compromiso: Optional[date]
    fecha_cierre: Optional[date]
    verificacion_eficacia: str
    vencido: bool = False
    acciones: list[AccionOut] = []


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    orden: int
    clausula: str
    texto: str
    critico: bool


class PlantillaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    clave: str
    nombre: str
    norma: str
    sector: str
    pais: str
    items: list[ItemOut] = []


class AuditoriaIn(BaseModel):
    plantilla_id: int
    area: str = ""
    fecha_programada: Optional[date] = None
    auditor_id: Optional[int] = None


class RespuestaIn(BaseModel):
    item_id: int
    resultado: Literal["cumple", "no_cumple", "na"]
    observacion: str = ""


class RespuestaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    item_id: int
    resultado: str
    observacion: str
    hallazgo_id: Optional[int]


class AuditoriaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    plantilla_id: int
    area: str
    fecha_programada: Optional[date]
    auditor_id: Optional[int]
    estado: str
    puntaje: Optional[int]
    respuestas: list[RespuestaOut] = []
