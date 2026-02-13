REQUEST: NUEVA PÁGINA “TENDENCIAS” + MIGRACIÓN DE SECCIONES DESDE INICIO (SIN REDISEÑAR COMPONENTES)

CONTEXTO
En la página principal (Inicio) actualmente existen dos secciones:
1) “Panorama del mercado inmobiliario en El Salvador” con 4 cards:
   - Precio medio venta
   - Renta media mensual
   - Activos hoy
   - Nuevos (7 días)
2) “Ranking del mercado inmobiliario en El Salvador” con 3 gráficos:
   - Zonas más caras
   - Zonas más económicas
   - Zonas más activas

OBJETIVO
Crear una nueva página llamada “Tendencias” y mover estas dos secciones desde Inicio hacia esa nueva página, manteniendo exactamente el mismo diseño, componentes y lógica de data existentes.

CAMBIO EN NAVIGATION BAR
- Agregar un tercer ítem de menú: “Tendencias”
- Debe seguir el mismo diseño, comportamiento y estado activo/hover que “Inicio” y “Evaluador”.
- Reutilizar los mismos componentes/clases/estilos del navbar (no crear un diseño nuevo).

MIGRACIÓN DE CONTENIDO
- Remover de la página Inicio las secciones:
  - “Panorama del mercado inmobiliario en El Salvador”
  - “Ranking del mercado inmobiliario en El Salvador”
- Insertar ambas secciones en la nueva página “Tendencias” en el mismo orden:
  1) Panorama (cards)
  2) Ranking (3 gráficos)
- Mantener:
  - el mismo layout, padding, títulos, subtítulos, pills “TOTAL/VENTA/RENTA”
  - los mismos servicios/métodos/procesos de cálculo y obtención de data
  - el mismo comportamiento de filtros si aplica (Total/Venta/Renta)
  - el indicador “LIVE” tal como está (sin texto adicional)

REGLAS
- No rediseñar visualmente las secciones; solo moverlas.
- No duplicar lógica ni re-implementar cálculos: extraer a componentes reutilizables si es necesario.
- La navegación debe funcionar igual que las páginas existentes (routing, estado activo del menú, etc.).

CRITERIOS DE ACEPTACIÓN
- Navbar muestra: “Inicio”, “Evaluador”, “Tendencias” con estilos/estados consistentes.
- Al entrar a “Tendencias” se ven ambas secciones exactamente como se veían en Inicio.
- Inicio ya no muestra esas dos secciones.
- Data y charts siguen funcionando sin regresiones (misma data, mismos procesos, misma interacción).
