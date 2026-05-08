from django.shortcuts import render, redirect, get_object_or_404
from .models import Producto, Pedido, ItemPedido, Categoria
import mercadopago
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
import json
from django.utils import timezone
from django.core.mail import send_mail
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum
from datetime import timedelta
import csv


sdk = mercadopago.SDK(settings.MERCADOPAGO_ACCESS_TOKEN)


def inicio(request):
    productos = Producto.objects.filter(activo=True).order_by("-destacado")

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

        if request.session.get("pedido_en_proceso"):
            messages.warning(request, "Ya hay un pedido en proceso.")
            return redirect("ver_carrito")

        request.session["pedido_en_proceso"] = True
        request.session.modified = True

        try:
            metodo_pago = request.POST.get("metodo_pago")

            for key, item in carrito.items():
                producto = get_object_or_404(Producto, id=int(key))

                if producto.stock <= 0:
                    messages.error(request, f"{producto.nombre} no tiene stock disponible.")
                    request.session["pedido_en_proceso"] = False
                    request.session.modified = True
                    return redirect("ver_carrito")

                if item["cantidad"] > producto.stock:
                    messages.error(
                        request,
                        f"Stock insuficiente para {producto.nombre}. Disponible: {producto.stock}."
                    )
                    request.session["pedido_en_proceso"] = False
                    request.session.modified = True
                    return redirect("ver_carrito")

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

            productos_texto = "\n".join([
                f"- {item.nombre_producto} x{item.cantidad}"
                for item in pedido.items.all()
            ])

            
#             send_mail(
#                     subject=f"Pedido #{pedido.id} recibido",
#                     message=f"""
# Hola {pedido.nombre},

# Recibimos tu pedido #{pedido.id}.

# Total: ${pedido.total}
# Método de pago: {pedido.get_metodo_pago_display()}
# Estado: {pedido.get_estado_display()}

# Podés ver tu pedido acá:
# https://rbjoyas.onrender.com/pedido/{pedido.id}/{pedido.token}/
# """,
#                     from_email=settings.EMAIL_HOST_USER,
#                     recipient_list=[pedido.email],
#                     fail_silently=True,
#                 )
            

            
#             send_mail(
#                     subject=f"NUEVO PEDIDO #{pedido.id}",
#                     message=f"""
# Nuevo pedido recibido

# Cliente: {pedido.nombre} {pedido.apellido}
# DNI: {pedido.dni}
# Teléfono: {pedido.telefono}
# Email: {pedido.email}

# Dirección:
# {pedido.direccion}, {pedido.ciudad}, {pedido.provincia}
# CP: {pedido.codigo_postal}

# Productos:
# {productos_texto}

# Total: ${pedido.total}
# Método de pago: {pedido.get_metodo_pago_display()}
# Estado: {pedido.get_estado_display()}

# Ver pedido:
# https://rbjoyas.onrender.com/pedido/{pedido.id}/{pedido.token}/
# """,
#                     from_email=settings.EMAIL_HOST_USER,
#                     recipient_list=[settings.EMAIL_VENDEDOR],
#                     fail_silently=True,
#                 )
            

            request.session["carrito"] = {}
            request.session["pedido_en_proceso"] = False
            request.session.modified = True

            if metodo_pago == "mercadopago":
                url_pago = crear_preferencia(pedido)
                return redirect(url_pago)

            if metodo_pago == "transferencia":
                return redirect("transferencia", pedido_id=pedido.id)

            return redirect("ver_pedido", pedido_id=pedido.id, token=pedido.token)

        except Exception as e:
            request.session["pedido_en_proceso"] = False
            request.session.modified = True
            print("Error creando pedido:", e)
            messages.error(request, "Ocurrió un error al crear el pedido. Intentá nuevamente.")
            return redirect("ver_carrito")

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
        "notification_url": "https://rbjoyas.onrender.com/webhook/mercadopago/",
        "back_urls": {
            "success": f"https://rbjoyas.onrender.com/pedido-exitoso/?pedido_id={pedido.id}",
            "failure": "https://rbjoyas.onrender.com/",
            "pending": "https://rbjoyas.onrender.com/",
        },
        "auto_return": "approved",
    }

    preference_response = sdk.preference().create(preference_data)
    response = preference_response.get("response", {})

    if "init_point" in response:
        return response["init_point"]

    if "sandbox_init_point" in response:
        return response["sandbox_init_point"]

    raise Exception(f"Mercado Pago no devolvió init_point: {response}")


def pago_exitoso(request):
    pedido_id = request.GET.get("pedido_id")
    pedido = None

    if pedido_id:
        pedido = Pedido.objects.filter(id=pedido_id).first()

    return render(request, "tienda/pago_exitoso.html", {
        "pedido": pedido
    })


@csrf_exempt
def mercadopago_webhook(request):
    if request.method != "POST":
        return HttpResponse(status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        data = {}

    payment_id = None

    if data.get("type") == "payment":
        payment_id = data.get("data", {}).get("id")

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

        return redirect(f"/pedido-exitoso/?pedido_id={pedido.id}")

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


@staff_member_required
def dashboard_admin(request):
    hoy = timezone.now()
    hace_30_dias = hoy - timedelta(days=30)

    fecha_desde = request.GET.get("desde")
    fecha_hasta = request.GET.get("hasta")
    estado = request.GET.get("estado")

    pedidos = Pedido.objects.all()

    if fecha_desde:
        pedidos = pedidos.filter(creado__date__gte=fecha_desde)

    if fecha_hasta:
        pedidos = pedidos.filter(creado__date__lte=fecha_hasta)

    if estado:
        pedidos = pedidos.filter(estado=estado)

    total_vendido = pedidos.filter(
        estado="pagado"
    ).aggregate(total=Sum("total"))["total"] or 0

    total_vendido_30_dias = Pedido.objects.filter(
        estado="pagado",
        creado__gte=hace_30_dias
    ).aggregate(total=Sum("total"))["total"] or 0

    pedidos_total = pedidos.count()
    pedidos_pagados = pedidos.filter(estado="pagado").count()
    pedidos_pendientes = pedidos.filter(estado="pendiente").count()
    pedidos_cancelados = pedidos.filter(estado="cancelado").count()

    transferencias_pendientes = pedidos.filter(
        metodo_pago="transferencia",
        estado="pendiente"
    ).count()

    mercado_pago_pendientes = pedidos.filter(
        metodo_pago="mercadopago",
        estado="pendiente"
    ).count()

    productos_bajo_stock = Producto.objects.filter(
        stock__lte=3,
        activo=True
    ).order_by("stock")

    ultimos_pedidos = pedidos.order_by("-creado")[:50]

    return render(request, "tienda/dashboard_admin.html", {
        "total_vendido": total_vendido,
        "total_vendido_30_dias": total_vendido_30_dias,
        "pedidos_total": pedidos_total,
        "pedidos_pagados": pedidos_pagados,
        "pedidos_pendientes": pedidos_pendientes,
        "pedidos_cancelados": pedidos_cancelados,
        "transferencias_pendientes": transferencias_pendientes,
        "mercado_pago_pendientes": mercado_pago_pendientes,
        "productos_bajo_stock": productos_bajo_stock,
        "ultimos_pedidos": ultimos_pedidos,
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
        "estado_actual": estado,
    })


@staff_member_required
def exportar_pedidos_csv(request):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="pedidos.csv"'
    response.write("\ufeff")

    writer = csv.writer(response, delimiter=";")

    writer.writerow([
        "ID", "Nombre", "Apellido", "DNI", "Email", "Telefono",
        "Provincia", "Ciudad", "Codigo Postal", "Direccion",
        "Detalle Direccion", "Metodo de pago", "Estado", "Total", "Fecha"
    ])

    pedidos = Pedido.objects.all()

    fecha_desde = request.GET.get("desde")
    fecha_hasta = request.GET.get("hasta")
    estado = request.GET.get("estado")

    if fecha_desde:
        pedidos = pedidos.filter(creado__date__gte=fecha_desde)

    if fecha_hasta:
        pedidos = pedidos.filter(creado__date__lte=fecha_hasta)

    if estado:
        pedidos = pedidos.filter(estado=estado)

    for p in pedidos.order_by("-creado"):
        writer.writerow([
            p.id,
            p.nombre,
            p.apellido,
            p.dni,
            p.email,
            p.telefono,
            p.provincia,
            p.ciudad,
            p.codigo_postal,
            p.direccion,
            p.detalle_direccion,
            p.get_metodo_pago_display(),
            p.get_estado_display(),
            p.total,
            p.creado.strftime("%d/%m/%Y %H:%M"),
        ])

    return response







from django.core.mail import send_mail
from django.http import HttpResponse


def test_email(request):

    send_mail(
        subject="Prueba Brevo",
        message="Si recibís esto, Brevo funciona.",
        from_email="rbjoyasdeplata@gmail.com",
        recipient_list=["TU_MAIL_REAL@gmail.com"],
        fail_silently=False,
    )

    return HttpResponse("Mail enviado")


def contacto(request):
    return render(request, 'tienda/contacto.html')