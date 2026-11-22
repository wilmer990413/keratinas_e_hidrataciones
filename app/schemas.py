from typing import Optional, List, Any
from pydantic import BaseModel, Field, field_validator, model_validator


class SchemaBase(BaseModel):
    class Config:
        extra = "ignore"
        str_strip_whitespace = True


class AuxiliarParticipacionSchema(SchemaBase):
    id: str = Field(..., min_length=1, description="ID del auxiliar")
    porcentaje: float = Field(..., gt=0, lt=100, description="Porcentaje de participación")


class VentaItemStockSchema(SchemaBase):
    productoId: str = Field(..., min_length=1)
    presentacionId: str = Field(..., min_length=1)
    cantidad: int = Field(..., gt=0)


class VentaComboStockSchema(SchemaBase):
    comboId: str = Field(..., min_length=1)
    cantidad: int = Field(..., gt=0)


class TransaccionCrearSchema(SchemaBase):
    id: str = Field(..., min_length=1)
    cliente: str = Field(..., min_length=1)
    tipoServicio: str = Field(..., min_length=1)
    adminShare: float = Field(default=0.0, ge=0)
    materiaPrimaShare: float = Field(default=0.0, ge=0)
    total: float = Field(default=0.0, ge=0)
    fleteTotal: float = Field(default=0.0, ge=0)
    invShare: Optional[float] = None
    inversionShare: Optional[float] = None
    gananciaInvShare: Optional[float] = None
    auxiliares: List[AuxiliarParticipacionSchema] = Field(default_factory=list)
    items: Optional[List[VentaItemStockSchema]] = Field(default_factory=list)
    combos: Optional[List[VentaComboStockSchema]] = Field(default_factory=list)

    @field_validator("cliente", "tipoServicio")
    @classmethod
    def no_vacio(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("El campo no puede estar vacío.")
        return s

    @model_validator(mode="after")
    def validar_shares(self):
        if self.inversionShare is not None and self.inversionShare < 0:
            raise ValueError("La inversión no puede ser negativa.")
        if self.gananciaInvShare is not None and self.gananciaInvShare < 0:
            raise ValueError("La ganancia del inversionista no puede ser negativa.")
        return self


class VentaItemEditarSchema(SchemaBase):
    id: Optional[int] = None
    productoId: str = Field(..., min_length=1)
    presentacionId: str = Field(..., min_length=1)
    cantidad: int = Field(..., gt=0)
    # Se conserva para compatibilidad con editores anteriores. El editor actual
    # envía además el desglose completo por presentación.
    precioUnitario: float = Field(default=0.0, ge=0)
    precioBase: Optional[float] = Field(default=None, ge=0)
    gananciaAdmin: Optional[float] = Field(default=None, ge=0)
    gananciaInv: Optional[float] = Field(default=None, ge=0)
    flete: Optional[float] = Field(default=None, ge=0)
    precioFinal: Optional[float] = Field(default=None, ge=0)


class TransaccionEditarSchema(SchemaBase):
    cliente: Optional[str] = None
    fechaHora: Optional[str] = None
    adminShare: Optional[float] = Field(default=None, ge=0)
    materiaPrimaShare: Optional[float] = Field(default=None, ge=0)
    inversionShare: Optional[float] = Field(default=None, ge=0)
    gananciaInvShare: Optional[float] = Field(default=None, ge=0)
    fleteTotal: Optional[float] = Field(default=None, ge=0)
    auxiliares: Optional[List[AuxiliarParticipacionSchema]] = None
    items: Optional[List[VentaItemEditarSchema]] = None


class ProductoPresentacionItemSchema(SchemaBase):
    presentacionId: str = Field(..., min_length=1)
    basePrice: Optional[float] = Field(default=0.0, ge=0)
    adminGain: Optional[float] = Field(default=0.0, ge=0)
    invGain: Optional[float] = Field(default=0.0, ge=0)
    flete: Optional[float] = Field(default=0.0, ge=0)


class ProductoGuardarSchema(SchemaBase):
    id: Optional[str] = None
    nombre: str = Field(..., min_length=1)
    stock: int = Field(default=0, ge=0)
    esAmpolleta: Optional[int] = 0
    inversionistaId: Optional[str] = None
    presentaciones: Optional[List[Any]] = None

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("El nombre del producto no puede estar vacío.")
        return s


class InversionistaGuardarSchema(SchemaBase):
    id: Optional[str] = None
    nombre: str = Field(..., min_length=1)
    documento: Optional[str] = ""
    telefono: Optional[str] = ""
    porcentajeGanancia: float = Field(default=0.0, ge=0, le=100)
    activo: Optional[bool] = True

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("El nombre del inversionista es obligatorio.")
        return s


class PresentacionGuardarSchema(SchemaBase):
    nombre: str = Field(..., min_length=1)
    factor: int = Field(..., gt=0)

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("El nombre de la presentación no puede estar vacío.")
        return s


class AuxiliarGuardarSchema(SchemaBase):
    id: Optional[str] = None
    nombre: str = Field(..., min_length=1)
    documento: Optional[str] = ""
    telefono: Optional[str] = ""
    activo: Optional[bool] = True

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("El nombre del auxiliar es obligatorio.")
        return s


class ComboItemGuardarSchema(SchemaBase):
    productoId: str = Field(..., min_length=1)
    presentacionId: Optional[str] = Field(default=None)
    cantidad: int = Field(..., gt=0)
    costoBase: Optional[float] = Field(default=0.0, ge=0)
    adminGain: Optional[float] = Field(default=0.0, ge=0)
    invGain: Optional[float] = Field(default=0.0, ge=0)
    flete: Optional[float] = Field(default=0.0, ge=0)


class ComboGuardarSchema(SchemaBase):
    id: Optional[str] = None
    nombre: str = Field(..., min_length=1)
    items: List[ComboItemGuardarSchema] = Field(default_factory=list)

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("El nombre del combo es obligatorio.")
        return s


class DescuentoNominaSchema(SchemaBase):
    concepto: str = Field(..., min_length=1)
    tipo: str = Field(..., pattern=r"^(fijo|porcentaje|monto)$")
    valor: float = Field(..., ge=0)
    aplicarA: Optional[str] = None
    destino: Optional[str] = None

    @model_validator(mode="after")
    def validar_destino_y_valor(self):
        if self.tipo == "porcentaje" and self.valor > 100:
            raise ValueError(f"El porcentaje de descuento no puede superar el 100%.")
        if not self.aplicarA and not self.destino:
            raise ValueError("Debe especificar el destinatario del descuento.")
        return self


def parse_payload(schema_cls, data: dict):
    """Valida un diccionario contra un schema Pydantic y retorna una instancia limpia o genera ValueError legible."""
    if not isinstance(data, dict):
        raise ValueError("El formato de los datos enviados debe ser un objeto JSON válido.")
    try:
        return schema_cls.model_validate(data)
    except Exception as err:
        # Extraer mensajes legibles de Pydantic
        if hasattr(err, "errors"):
            mensajes = []
            for e in err.errors():
                loc = " -> ".join(str(x) for x in e.get("loc", []))
                msg = e.get("msg", "Dato inválido")
                mensajes.append(f"[{loc}]: {msg}" if loc else msg)
            raise ValueError(f"Error de validación: {'; '.join(mensajes)}")
        raise ValueError(str(err))
