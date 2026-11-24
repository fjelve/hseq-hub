from datetime import datetime, date

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


def _now():
    return datetime.utcnow()


class Empresa(Base):
    __tablename__ = "empresas"
    id = Column(Integer, primary_key=True)
    nombre = Column(String(200), nullable=False)
    sector = Column(String(30), nullable=False, default="mineria")  # mineria | industria
    pais = Column(String(10), nullable=False, default="chile")  # chile | peru
    creada_en = Column(DateTime, default=_now)


class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    nombre = Column(String(150), nullable=False)
    email = Column(String(200), nullable=False, unique=True, index=True)
    password_hash = Column(String(200), nullable=False)
    rol = Column(String(20), nullable=False, default="responsable")  # admin | auditor | responsable
    activo = Column(Boolean, default=True)
    creado_en = Column(DateTime, default=_now)


class Hallazgo(Base):
    """No conformidad / observación / incidente que dispara el ciclo CAPA."""
    __tablename__ = "hallazgos"
    __table_args__ = (UniqueConstraint("empresa_id", "codigo"),)
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    codigo = Column(String(30), nullable=False)
    titulo = Column(String(250), nullable=False)
    descripcion = Column(Text, default="")
    origen = Column(String(30), default="auditoria")  # auditoria | inspeccion | incidente | otro
    norma = Column(String(40), default="")
    area = Column(String(120), default="")
    severidad = Column(String(10), default="media")  # baja | media | alta | critica
    estado = Column(String(20), default="abierto")  # abierto | en_proceso | en_verificacion | cerrado
    causa_raiz = Column(Text, default="")
    metodo_causa = Column(String(30), default="")  # 5_porques | ishikawa | otro
    responsable_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    fecha_compromiso = Column(Date, nullable=True)
    fecha_cierre = Column(Date, nullable=True)
    verificacion_eficacia = Column(Text, default="")
    vencido_notificado = Column(Boolean, default=False)
    creado_en = Column(DateTime, default=_now)

    acciones = relationship("Accion", back_populates="hallazgo", cascade="all, delete-orphan")
    responsable = relationship("Usuario", foreign_keys=[responsable_id])


class Accion(Base):
    __tablename__ = "acciones"
    id = Column(Integer, primary_key=True)
    hallazgo_id = Column(Integer, ForeignKey("hallazgos.id"), nullable=False, index=True)
    tipo = Column(String(15), default="correctiva")  # inmediata | correctiva | preventiva
    descripcion = Column(Text, nullable=False)
    responsable_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    fecha_compromiso = Column(Date, nullable=True)
    completada = Column(Boolean, default=False)
    fecha_completada = Column(Date, nullable=True)
    evidencia = Column(Text, default="")

    hallazgo = relationship("Hallazgo", back_populates="acciones")


class PlantillaAuditoria(Base):
    """Checklist reutilizable. empresa_id NULL = plantilla global del sistema."""
    __tablename__ = "plantillas"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=True, index=True)
    clave = Column(String(60), nullable=False, index=True)
    nombre = Column(String(200), nullable=False)
    norma = Column(String(40), nullable=False)
    sector = Column(String(30), nullable=False)  # mineria | industria | todos
    pais = Column(String(10), nullable=False, default="todos")  # chile | peru | todos

    items = relationship("PlantillaItem", back_populates="plantilla",
                         cascade="all, delete-orphan", order_by="PlantillaItem.orden")


class PlantillaItem(Base):
    __tablename__ = "plantilla_items"
    id = Column(Integer, primary_key=True)
    plantilla_id = Column(Integer, ForeignKey("plantillas.id"), nullable=False, index=True)
    orden = Column(Integer, default=0)
    clausula = Column(String(40), default="")
    texto = Column(Text, nullable=False)
    critico = Column(Boolean, default=False)

    plantilla = relationship("PlantillaAuditoria", back_populates="items")


class Auditoria(Base):
    __tablename__ = "auditorias"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    plantilla_id = Column(Integer, ForeignKey("plantillas.id"), nullable=False)
    area = Column(String(120), default="")
    fecha_programada = Column(Date, default=date.today)
    auditor_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    estado = Column(String(15), default="programada")  # programada | en_curso | cerrada
    puntaje = Column(Integer, nullable=True)  # % cumplimiento al cerrar
    creada_en = Column(DateTime, default=_now)

    plantilla = relationship("PlantillaAuditoria")
    respuestas = relationship("Respuesta", back_populates="auditoria", cascade="all, delete-orphan")


class Respuesta(Base):
    __tablename__ = "respuestas"
    __table_args__ = (UniqueConstraint("auditoria_id", "item_id"),)
    id = Column(Integer, primary_key=True)
    auditoria_id = Column(Integer, ForeignKey("auditorias.id"), nullable=False, index=True)
    item_id = Column(Integer, ForeignKey("plantilla_items.id"), nullable=False)
    resultado = Column(String(10), nullable=False)  # cumple | no_cumple | na
    observacion = Column(Text, default="")
    hallazgo_id = Column(Integer, ForeignKey("hallazgos.id"), nullable=True)

    auditoria = relationship("Auditoria", back_populates="respuestas")
    item = relationship("PlantillaItem")


class Incidente(Base):
    __tablename__ = "incidentes"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    fecha = Column(Date, nullable=False, default=date.today)
    # accidente_ctp = con tiempo perdido | accidente_stp = sin tiempo perdido
    tipo = Column(String(20), nullable=False)  # accidente_ctp | accidente_stp | casi_accidente | ambiental | dano_propiedad
    severidad = Column(String(10), default="media")
    area = Column(String(120), default="")
    descripcion = Column(Text, default="")
    dias_perdidos = Column(Integer, default=0)
    hallazgo_id = Column(Integer, ForeignKey("hallazgos.id"), nullable=True)
    creado_en = Column(DateTime, default=_now)


class HorasTrabajadas(Base):
    __tablename__ = "horas_trabajadas"
    __table_args__ = (UniqueConstraint("empresa_id", "periodo"),)
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    periodo = Column(String(7), nullable=False)  # YYYY-MM
    horas = Column(Integer, nullable=False)


class RequisitoLegal(Base):
    """Permisos, licencias, certificaciones y monitoreos con vencimiento."""
    __tablename__ = "requisitos_legales"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    nombre = Column(String(250), nullable=False)
    tipo = Column(String(20), default="permiso")  # permiso | licencia | certificacion | monitoreo | norma
    entidad = Column(String(150), default="")
    responsable_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    fecha_vencimiento = Column(Date, nullable=True)
    notas = Column(Text, default="")
    notificado = Column(Boolean, default=False)


class IndicadorAmbiental(Base):
    __tablename__ = "indicadores_ambientales"
    __table_args__ = (UniqueConstraint("empresa_id", "periodo", "tipo"),)
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    periodo = Column(String(7), nullable=False)
    tipo = Column(String(30), nullable=False)  # energia_kwh | agua_m3 | residuos_peligrosos_kg | residuos_no_peligrosos_kg | combustible_l
    valor = Column(Float, nullable=False)
