from django.urls import path
from . import views

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("carrito/", views.ver_carrito, name="ver_carrito"),
    path("agregar/<int:producto_id>/", views.agregar_al_carrito, name="agregar_al_carrito"),
    path("eliminar/<int:producto_id>/", views.eliminar_del_carrito, name="eliminar_del_carrito"),
    path("actualizar/<int:producto_id>/", views.actualizar_carrito, name="actualizar_carrito"),
    path("checkout/", views.checkout, name="checkout"),
    path("pedido-exitoso/", views.pago_exitoso, name="pedido_exitoso"),
    path("webhook/mercadopago/", views.mercadopago_webhook, name="mercadopago_webhook"),
    path("transferencia/<int:pedido_id>/", views.transferencia, name="transferencia"),
    path("pedido/<int:pedido_id>/<uuid:token>/", views.ver_pedido, name="ver_pedido"),    
    path("catalogo/", views.catalogo, name="catalogo"),
    path("categoria/<slug:slug>/", views.productos_por_categoria, name="productos_por_categoria"),
    path("producto/<slug:slug>/", views.detalle_producto, name="detalle_producto"),
    path("admin-panel/", views.dashboard_admin, name="dashboard_admin"),
    path("exportar-pedidos/", views.exportar_pedidos_csv, name="exportar_pedidos"),
    path("test-email/", views.test_email, name="test_email"),
    ]