from django.shortcuts import render
from .models import Producto
from django.shortcuts import redirect, get_object_or_404
from .models import Pedido, ItemPedido
import mercadopago
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
import json
from django.utils import timezone
from django.core.mail import send_mail
from .models import Producto, Categoria
from django.contrib import messages


sdk = mercadopago.SDK(settings.MERCADOPAGO_ACCESS_TOKEN)



def inicio(request):
    productos = Producto.objects.filter(activo=True)

    return render(request, "tienda/inicio.html", {
        "productos": productos
    })


def agregar_al_carrito(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id)

    cantidad = int(request.POST.get("cantidad", 1))

    carrito = request.session.get("carrito", {})

    if str(producto_id) in carrito:
        carrito[str(producto_id)]["cantidad"] += cantidad
    else:
        carrito[str(producto_id)] = {
            "nombre": producto.nombre,
            "precio": float(producto.precio),
            "cantidad": cantidad
        }

    request.session["carrito"] = carrito

    return redirect("inicio")



def ver_carrito(request):
    carrito = request.session.get("carrito", {})
    total = 0

    for key, item in carrito.items():
        item["subtotal"] = item["precio"] * item["cantidad"]
        total += item["subtotal"]

    return render(request, "tienda/carrito.html", {
        "carrito": carrito,
        "total": total
    })


def eliminar_del_carrito(request, producto_id):
    carrito = request.session.get("carrito", {})

    if str(producto_id) in carrito:
        del carrito[str(producto_id)]

    request.session["carrito"] = carrito

    return redirect("ver_carrito")


def actualizar_carrito(request, producto_id):
    if request.method == "POST":
        cantidad = int(request.POST.get("cantidad", 1))
        carrito = request.session.get("carrito", {})

        if str(producto_id) in carrito:
            if cantidad > 0:
                carrito[str(producto_id)]["cantidad"] = cantidad
            else:
                del carrito[str(producto_id)]

        request.session["carrito"] = carrito

    return redirect("ver_carrito")







def checkout(request):
    carrito = request.session.get("carrito", {})

    if not carrito:
        return redirect("inicio")

    total = 0
    for item in carrito.values():
        total += item["precio"] * item["cantidad"]

    if request.method == "POST":
        metodo_pago = request.POST.get("metodo_pago")

        # 1. Validar stock ANTES de crear el pedido
        for key, item in carrito.items():
            producto = get_object_or_404(Producto, id=int(key))

            if producto.stock <= 0:
                messages.error(request, f"{producto.nombre} no tiene stock disponible.")
                return redirect("ver_carrito")

            if item["cantidad"] > producto.stock:
                messages.error(
                    request,
                    f"Stock insuficiente para {producto.nombre}. Disponible: {producto.stock}."
                )
                return redirect("ver_carrito")

        # 2. Crear pedido solo si hay stock
        pedido = Pedido.objects.create(
            usuario=request.user if request.user.is_authenticated else None,
            nombre=request.POST.get("nombre"),
            apellido=request.POST.get("apellido"),
            dni=request.POST.get("dni"),
            email=request.POST.get("email"),
            telefono=request.POST.get("telefono"),
            provincia=request.POST.get("provincia"),
            ciudad=request.POST.get("ciudad"),
            codigo_postal=request.POST.get("codigo_postal"),
            direccion=request.POST.get("direccion"),
            detalle_direccion=request.POST.get("detalle_direccion"),
            metodo_pago=metodo_pago,
            total=total
        )

        # 3. Crear items y descontar stock
        for key, item in carrito.items():
            producto = get_object_or_404(Producto, id=int(key))

            ItemPedido.objects.create(
                pedido=pedido,
                producto=producto,
                nombre_producto=item["nombre"],
                precio=item["precio"],
                cantidad=item["cantidad"]
            )

            producto.stock -= item["cantidad"]
            producto.save()

        send_mail(
            subject=f"Pedido #{pedido.id} recibido",
            message=f"""
Hola {pedido.nombre},

Recibimos tu pedido #{pedido.id}.

Total: ${pedido.total}
Método de pago: {pedido.get_metodo_pago_display()}
Estado: {pedido.get_estado_display()}

Podés ver tu pedido acá:
http://127.0.0.1:8005/pedido/{pedido.id}/{pedido.token}/
""",
            from_email=None,
            recipient_list=[pedido.email],
            fail_silently=True,
        )

        request.session["carrito"] = {}

        if metodo_pago == "mercadopago":
            url_pago = crear_preferencia(pedido)
            return redirect(url_pago)

        if metodo_pago == "transferencia":
            return redirect("transferencia", pedido_id=pedido.id)

        return redirect("ver_pedido", pedido_id=pedido.id, token=pedido.token)

    return render(request, "tienda/checkout.html", {
        "carrito": carrito,
        "total": total
    })
def crear_preferencia(pedido):
    items = []

    for item in pedido.items.all():
        items.append({
            "title": item.nombre_producto,
            "quantity": int(item.cantidad),
            "unit_price": float(item.precio),
            "currency_id": "ARS",
        })

    preference_data = {
        "items": items,
        "external_reference": str(pedido.id),

        "notification_url": "https://simplify-demanding-favored.ngrok-free.dev/webhook/mercadopago/",

        "back_urls": {
            "success": "https://simplify-demanding-favored.ngrok-free.dev/pago-exitoso/",
            "failure": "https://simplify-demanding-favored.ngrok-free.dev/",
            "pending": "https://simplify-demanding-favored.ngrok-free.dev/",
        },

        "auto_return": "approved",
    }

    preference_response = sdk.preference().create(preference_data)

    print("RESPUESTA MERCADO PAGO:", preference_response)

    response = preference_response.get("response", {})

    if "init_point" in response:
        return response["init_point"]

    if "sandbox_init_point" in response:
        return response["sandbox_init_point"]

    raise Exception(f"Mercado Pago no devolvió init_point: {response}")

def pago_exitoso(request):
    return render(request, "tienda/pago_exitoso.html")







@csrf_exempt
def mercadopago_webhook(request):
    if request.method != "POST":
        return HttpResponse(status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        data = {}

    payment_id = None

    # Formato típico webhook
    if data.get("type") == "payment":
        payment_id = data.get("data", {}).get("id")

    # Formato alternativo/IPN
    if not payment_id:
        payment_id = request.GET.get("id") or request.GET.get("data.id")

    if not payment_id:
        return HttpResponse(status=200)

    try:
        payment_info = sdk.payment().get(payment_id)
        payment = payment_info.get("response", {})

        estado_pago = payment.get("status")
        pedido_id = payment.get("external_reference")

        if pedido_id:
            pedido = Pedido.objects.get(id=pedido_id)
            pedido.mercadopago_payment_id = str(payment_id)
            pedido.mercadopago_status = estado_pago

            if estado_pago == "approved":
                pedido.estado = "pagado"
                pedido.pagado_en = timezone.now()

            pedido.save()

    except Exception as e:
        print("Error webhook Mercado Pago:", e)

    return HttpResponse(status=200)




def transferencia(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)

    if request.method == "POST":
        comprobante = request.FILES.get("comprobante")

        if comprobante:
            pedido.comprobante_transferencia = comprobante
            pedido.save()

        return redirect("pedido_exitoso")

    return render(request, "tienda/transferencia.html", {
        "pedido": pedido
    })



def ver_pedido(request, pedido_id, token):
    pedido = get_object_or_404(Pedido, id=pedido_id, token=token)

    return render(request, "tienda/ver_pedido.html", {
        "pedido": pedido
    })





def catalogo(request):
    categorias = Categoria.objects.filter(activa=True)
    productos = Producto.objects.filter(activo=True)

    return render(request, "tienda/catalogo.html", {
        "categorias": categorias,
        "productos": productos,
    })


def productos_por_categoria(request, slug):
    categoria = get_object_or_404(Categoria, slug=slug, activa=True)
    productos = Producto.objects.filter(categoria=categoria, activo=True)
    categorias = Categoria.objects.filter(activa=True)

    return render(request, "tienda/catalogo.html", {
        "categorias": categorias,
        "productos": productos,
        "categoria_actual": categoria,
    })


def detalle_producto(request, slug):
    producto = get_object_or_404(Producto, slug=slug, activo=True)

    return render(request, "tienda/detalle_producto.html", {
        "producto": producto,
    })