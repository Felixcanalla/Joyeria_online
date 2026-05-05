from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
import uuid


class Categoria(models.Model):
    nombre = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nombre)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.CASCADE,
        related_name="productos"
    )
    nombre = models.CharField(max_length=150)
    slug = models.SlugField(unique=True, blank=True)
    descripcion = models.TextField(blank=True)
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    imagen = models.ImageField(upload_to="productos/", blank=True, null=True)
    activo = models.BooleanField(default=True)
    destacado = models.BooleanField(default=False)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        ordering = ["-creado"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nombre)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre


class Pedido(models.Model):



    METODOS_PAGO = [
        ("efectivo", "Efectivo al retirar"),
        ("transferencia", "Transferencia"),
        ("mercadopago", "Mercado Pago"),
    ]

    ESTADOS = [
        ("pendiente", "Pendiente"),
        ("pagado", "Pagado"),
        ("preparacion", "En preparación"),
        ("enviado", "Enviado"),
        ("cancelado", "Cancelado"),
    ]

    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    token = models.UUIDField(default=uuid.uuid4, editable=False)
    # Datos del comprador
    nombre = models.CharField(max_length=150)
    apellido = models.CharField(max_length=150, blank=True)
    dni = models.CharField(max_length=20, blank=True)
    email = models.EmailField()
    telefono = models.CharField(max_length=30)

    # Datos de envío
    provincia = models.CharField(max_length=100, blank=True)
    ciudad = models.CharField(max_length=100, blank=True)
    codigo_postal = models.CharField(max_length=20, blank=True)
    direccion = models.CharField(max_length=255, blank=True)
    detalle_direccion = models.CharField(
        max_length=255,
        blank=True,
        help_text="Piso, departamento, entre calles, referencias, etc."
    )

    # Pago
    metodo_pago = models.CharField(max_length=20, choices=METODOS_PAGO)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default="pendiente"
    )

    comprobante_transferencia = models.ImageField(
        upload_to="comprobantes/",
        blank=True,
        null=True
    )

    mercadopago_payment_id = models.CharField(max_length=100, blank=True, null=True)
    mercadopago_status = models.CharField(max_length=50, blank=True, null=True)
    pagado_en = models.DateTimeField(blank=True, null=True)

    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"
        ordering = ["-creado"]

    def __str__(self):
        return f"Pedido #{self.id} - {self.nombre} {self.apellido}"

class ItemPedido(models.Model):
    pedido = models.ForeignKey(
        Pedido,
        on_delete=models.CASCADE,
        related_name="items"
    )
    producto = models.ForeignKey(
        Producto,
        on_delete=models.SET_NULL,
        null=True
    )

    nombre_producto = models.CharField(max_length=150)
    precio = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cantidad = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = "Item del pedido"
        verbose_name_plural = "Items del pedido"

    def subtotal(self):
        precio = self.precio if self.precio is not None else 0
        cantidad = self.cantidad if self.cantidad is not None else 0
        return precio * cantidad

    def __str__(self):
        return f"{self.nombre_producto} x {self.cantidad}"