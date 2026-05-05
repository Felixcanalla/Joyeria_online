from django.contrib import admin
from .models import Categoria, Producto, Pedido, ItemPedido
from django.utils.html import format_html





@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "slug", "activa")
    list_filter = ("activa",)
    search_fields = ("nombre",)
    prepopulated_fields = {"slug": ("nombre",)}


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = (
        "nombre",
        "categoria",
        "precio",
        "stock",
        "activo",
        "destacado",
        "creado",
    )
    list_filter = ("categoria", "activo", "destacado")
    search_fields = ("nombre", "descripcion")
    prepopulated_fields = {"slug": ("nombre",)}
    list_editable = ("precio", "stock", "activo", "destacado")
    readonly_fields = ("creado", "actualizado")


class ItemPedidoInline(admin.TabularInline):
    model = ItemPedido
    extra = 0
    readonly_fields = ("producto", "nombre_producto", "precio", "cantidad", "subtotal")
    can_delete = False

    def subtotal(self, obj):
        return obj.subtotal()


from django.utils.html import format_html


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):

    def ver_comprobante(self, obj):
        if obj.comprobante_transferencia:
            return format_html(
                '<a href="{}" target="_blank">Ver comprobante</a>',
                obj.comprobante_transferencia.url
            )
        return "Sin comprobante"

    ver_comprobante.short_description = "Comprobante"

    list_display = (
        "id",
        "nombre",
        "apellido",
        "dni",
        "detalle_direccion",
        "ciudad",
        "provincia",
        "email",
        "telefono",
        "metodo_pago",
        "total",
        "estado",
        "ver_comprobante",
        "mercadopago_status",
        "mercadopago_payment_id",
        "pagado_en",
        "creado",
    )

    list_filter = ("metodo_pago", "estado", "creado")
    search_fields = ("nombre", "email", "telefono")
    list_editable = ("estado",)

    readonly_fields = (
        "usuario",
        "nombre",
        "apellido",
        "dni",
        "provincia",
        "ciudad",
        "codigo_postal",
        "detalle_direccion",
        
        "email",
        "telefono",
        "direccion",
        "metodo_pago",
        "total",
        "estado",
        "comprobante_transferencia",
        "ver_comprobante",
        "mercadopago_payment_id",
        "mercadopago_status",
        "pagado_en",
        "creado",
    )

    inlines = [ItemPedidoInline]