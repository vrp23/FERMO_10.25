Módulo de Gestión de Compra-Venta de Cheques para Odoo 17 CE
Este módulo implementa la gestión completa de operaciones de compra y venta de cheques, con las siguientes características:

Características principales

Gestión completa de cheques: Registro, compra individual o múltiple, venta individual o múltiple, anulación y gestión de rechazos.
Dashboard principal: Con acceso rápido a las operaciones de compra y venta, y visualización de las últimas compras y cheques disponibles.
Flujo de estados: Borrador -> Disponible -> Vendido/Anulado/Rechazado.
Wallet de clientes/proveedores: Seguimiento de saldo en ARS para cada contacto con historial de transacciones.
Fórmulas configurables: Personalización de cálculos para pesificación, interés y precios.
Sistema de alertas avanzado:
   - Alerta de vencimientos: Sistema visual de alertas para cheques próximos a vencer (30, 15, 7 días).
   - Alerta de disponibilidad: Indicación de cuándo el cheque estará disponible para cobro.
Checklist de validación: Verificación de emisor, irregularidades y firma.
Gestión de fechas: Control de fecha de emisión, fecha de pago/cobro y fecha de vencimiento (calculada).
Compra múltiple: Capacidad de comprar varios cheques simultáneamente a un mismo proveedor.
Venta múltiple: Capacidad de vender varios cheques simultáneamente a un mismo cliente.
Gestión de rechazos: Proceso completo para manejar cheques rechazados, incluyendo compensaciones.
Tasas configurables: Posibilidad de modificar tasas de pesificación e interés para cada cheque o en bloque.
Adjuntos de imágenes: Posibilidad de adjuntar frente y dorso de los cheques.
Grupos de seguridad: Gestor, Supervisor y Solo lectura.

Flujo de operación

Compra de cheques:

Opción de compra individual o múltiple
Para compra múltiple: seleccionar un proveedor, agregar cheques, ajustar tasas
Completar los datos de cada cheque (fechas, montos, banco) y el checklist
Confirmar la compra (todos los cheques pasan a estado "Disponible")
Se genera un único movimiento en la wallet del proveedor con el monto total


Venta de cheques:

Opción de venta individual o múltiple
Para venta múltiple: seleccionar un cliente, agregar cheques, ajustar tasas
Confirmar la venta (todos los cheques pasan a estado "Vendido")
Se genera un movimiento en la wallet del cliente con el monto total


Gestión de rechazos:

Seleccionar un cheque en estado "Disponible" o "Vendido"
Iniciar el proceso de rechazo proporcionando un motivo
Decidir si se quiere revertir la operación de compra y/o venta
Indicar los montos de compensación (pueden diferir de los montos originales)
Se generan movimientos de compensación en la wallet del proveedor y/o cliente


Configuración

Bancos: Alta de bancos con nombre y código.
Fórmulas de cálculo: Configuración de las fórmulas para los valores calculados.
Grupos de seguridad: Asignación de permisos para las distintas operaciones.

Estructura del código
El módulo está organizado en varios archivos para facilitar el mantenimiento:

Modelos principales:

chequera_check.py: Definición base del modelo de cheque
chequera_check_compute.py: Métodos de cálculo para fechas y valores
chequera_check_operations.py: Operaciones y acciones sobre cheques
chequera_purchase_wizard.py: Wizard para compra múltiple
chequera_sale_wizard.py: Wizard para venta múltiple
chequera_rejection_wizard.py: Wizard para gestión de rechazos
chequera_wallet.py: Gestión de carteras de clientes/proveedores
chequera_bank.py: Gestión de bancos
chequera_formula.py: Configuración de fórmulas de cálculo
partner_inherit.py: Extensiones al modelo de contactos


Vistas principales:

chequera_dashboard_view.xml: Dashboard principal
chequera_check_view.xml: Vistas para cheques
chequera_purchase_wizard_view.xml: Vistas para el wizard de compra múltiple
chequera_sale_wizard_view.xml: Vistas para el wizard de venta múltiple
chequera_rejection_wizard_view.xml: Vistas para el wizard de rechazo
chequera_wallet_view.xml: Vistas para movimientos de wallet
chequera_menus.xml: Estructura de menús del módulo


Dependencias

Módulo base
Módulo mail (para el tracking y chatter)
Módulo web (para assets)

Desarrollado por
VRP - Virtual Remote Partner

Información para soporte futuro
Para continuar el desarrollo en futuras sesiones, es importante tener en cuenta:

Estructura modular: El código está dividido en archivos más pequeños para facilitar el mantenimiento:

Modelo principal (chequera_check.py)
Cálculos (chequera_check_compute.py)
Operaciones (chequera_check_operations.py)
Wizard de compra (chequera_purchase_wizard.py)
Wizard de venta (chequera_sale_wizard.py)
Wizard de rechazo (chequera_rejection_wizard.py)


Compatibilidad con Odoo 17 CE: Se han tenido en cuenta las particularidades de esta versión:

No se utilizan dominios con company_type
Se han adaptado las vistas XML según las recomendaciones de Odoo 17
Se utilizan expresiones directas para atributos invisibles en lugar de attrs y states
Se respeta el orden de carga de archivos para evitar problemas de referencia


Puntos pendientes para futuras mejoras:

Mejorar la actualización de totales en tiempo real al modificar tasas
Optimizar la experiencia de usuario al agregar/editar cheques en compras/ventas múltiples
Asegurar que las tablas del dashboard siempre muestren datos actualizados
Añadir reportes estadísticos sobre cheques rechazados
Implementar un sistema de notificaciones para cheques próximos a vencer


Flujos importantes:

Los botones del dashboard inician los procesos de compra/venta directamente
La compra/venta individual son casos particulares de operaciones múltiples (1 cheque)
La actualización masiva de tasas se aplica solo a los cheques de la operación actual
Los rechazos generan movimientos de compensación registrados y rastreables


Áreas para futuros desarrollos:

Reportes y análisis de operaciones
Integración con contabilidad
Gestión avanzada de permisos y aprobaciones
Mejoras en la interfaz de usuario
Dashboard estadístico más completo con gráficos