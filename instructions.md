TÍTULO
OPTIMIZACIÓN SEO + PERFORMANCE EN /TENDENCIAS (SIN CAMBIOS VISUALES NI FUNCIONALES)

CONTEXTO
PageSpeed Insights (mobile) está marcando puntos de performance que impactan LCP, especialmente: (a) recursos render-blocking (CSS) y (b) “Legacy JavaScript” (polyfills/transpilación innecesaria). El objetivo es optimizar carga y SEO manteniendo 100% intactos: diseño, estilos, componentes, layout, copy y lógica funcional.

REGLAS / NO TOCAR
- No cambiar UI/UX, estilos, spacing, colores, tipografías, componentes ni estructura visual.
- No eliminar features ni modificar flujos (solo optimización: carga, bundle, caching, metadata).
- Cualquier refactor debe ser “no visual diff” (misma apariencia) y “no behavior diff”.

OBJETIVO
- Reducir/neutralizar advertencias de PSI: “render-blocking resources” y “legacy JavaScript”.
- Mejorar TTI/LCP sin alterar el DOM visible.
- Fortalecer SEO de /tendencias (metadata + indexación) sin tocar diseño.

TAREAS (PERFORMANCE)
1) ELIMINAR/REDUCIR RENDER-BLOCKING (CSS)
   - Identificar qué está metiendo CSS en el chunk crítico (/static/css/*.css) y por qué se vuelve bloqueante.
   - Reducir CSS crítico SIN cambiar estilos: remover CSS no usado/duplicado, asegurar que Tailwind/content/purge esté correcto, y mover CSS estrictamente “page-only” a carga por ruta/componente (misma salida visual).
   - Meta: bajar tamaño del CSS crítico o evitar que CSS “no necesario para above-the-fold” quede en el critical path. (Guía: render-blocking resources). :contentReference[oaicite:0]{index=0}

2) EVITAR “LEGACY JAVASCRIPT” PARA BROWSERS MODERNOS
   - Auditar si hay: polyfills manuales, core-js, targets demasiado amplios (browserslist), o configuración de build que transpila de más.
   - Ajustar configuración para que el bundle enviado a navegadores modernos no cargue transforms/polyfills innecesarios, manteniendo compatibilidad según lo requerido por el proyecto.
   - Validar contra “Supported Browsers” de Next y asegurar que no se esté forzando compatibilidad legacy que infla el JS. :contentReference[oaicite:1]{index=1}

3) DIFERIR JS PESADO SIN CAMBIAR UI
   - Mantener el mismo contenido visible, pero cargar librerías pesadas (ej. gráficos) de forma diferida/condicional:
     - Lazy-load cuando el bloque entra en viewport (IntersectionObserver) o después de “first paint”.
     - Evitar que la librería de charts bloquee el render inicial si el contenido está below-the-fold.
   - Esto no cambia el diseño; solo cambia el “cuándo” se carga.

4) CACHE PARA QUE LA PÁGINA SEA “INSTANTÁNEA” AL REGRESAR
   - Implementar caching/revalidación (server o client) para que, al navegar fuera y volver a /tendencias, los datos y series de charts se pinten inmediatamente desde cache (y luego revaliden en background).
   - Usar el mecanismo de caching/revalidating del framework (Next: fetch cache/revalidateTag/unstable_cache, etc.) con TTL razonable y claves por filtro/tipo. :contentReference[oaicite:2]{index=2}

TAREAS (SEO, SIN CAMBIOS VISUALES)
5) METADATA COMPLETA EN /TENDENCIAS
   - Definir title/description únicos, canonical, OpenGraph/Twitter y metadata básica para indexación usando la API/conventions del framework (Next: Metadata API / generateMetadata / file conventions). :contentReference[oaicite:3]{index=3}
   - Asegurar jerarquía semántica correcta (H1 único, etc.) sin cambiar estilos (solo tags si aplica).

6) INDEXACIÓN
   - Confirmar robots/meta robots correcto para permitir indexación de /tendencias cuando aplique.
   - Incluir sitemap/robots según prácticas recomendadas (sin modificar UI). :contentReference[oaicite:4]{index=4}

CRITERIOS DE ACEPTACIÓN
- No hay cambios visuales perceptibles (comparación antes/después por screenshots).
- PSI Mobile mejora y reduce/mitiga:
  - Render-blocking resources (CSS) o su impacto en LCP. :contentReference[oaicite:5]{index=5}
  - “Legacy JavaScript” (menos wasted bytes / menos polyfills/transforms). :contentReference[oaicite:6]{index=6}
- Volver a /tendencias tras navegar a otra ruta carga charts y datos en ~0s percibido (cache warm) + revalidación silenciosa.
- SEO: metadata/canonical/OG listos y consistentes sin cambios de diseño. :contentReference[oaicite:7]{index=7}



Render blocking requests Est savings of 300 ms
Requests are blocking the page's initial render, which may delay LCP. Deferring or inlining can move these network requests out of the critical path.LCPFCPUnscored
URL
Transfer Size
Duration
vercel.app 1st party
20.5 KiB	300 ms
…chunks/6ac3d97369e71de6.css(sivarcasas.vercel.app)
20.5 KiB
300 ms
Legacy JavaScript Est savings of 14 KiB
Polyfills and transforms enable older browsers to use new JavaScript features. However, many aren't necessary for modern browsers. Consider modifying your JavaScript build process to not transpile Baseline features, unless you know you must support older browsers. Learn why most sites can deploy ES6+ code without transpilingLCPFCPUnscored
URL
Wasted bytes
vercel.app 1st party
13.7 KiB
…chunks/19deb65481cb608d.js(sivarcasas.vercel.app)
13.7 KiB
…chunks/19deb65481cb608d.js:1:5385(sivarcasas.vercel.app)
Array.prototype.at
…chunks/19deb65481cb608d.js:1:4773(sivarcasas.vercel.app)
Array.prototype.flat
…chunks/19deb65481cb608d.js:1:4886(sivarcasas.vercel.app)
Array.prototype.flatMap
…chunks/19deb65481cb608d.js:1:5262(sivarcasas.vercel.app)
Object.fromEntries
…chunks/19deb65481cb608d.js:1:5520(sivarcasas.vercel.app)
Object.hasOwn
…chunks/19deb65481cb608d.js:1:4515(sivarcasas.vercel.app)
String.prototype.trimEnd
…chunks/19deb65481cb608d.js:1:4430(sivarcasas.vercel.app)
String.prototype.trimStart
Network dependency tree
Avoid chaining critical requests by reducing the length of chains, reducing the download size of resources, or deferring the download of unnecessary resources to improve page load.LCPUnscored
Maximum critical path latency: 279 ms
Initial Navigation
/tendencias(sivarcasas.vercel.app) - 196 ms, 6.09 KiB
…chunks/6ac3d97369e71de6.css(sivarcasas.vercel.app) - 279 ms, 20.48 KiB
Preconnected origins
preconnect hints help the browser establish a connection earlier in the page load, saving time when the first request for that origin is made. The following are the origins that the page preconnected to.
no origins were preconnected
Preconnect candidates
Add preconnect hints to your most important origins, but try to use no more than 4.
No additional origins are good candidates for preconnecting


Reduce unused JavaScript Est savings of 102 KiB
Reduce unused JavaScript and defer loading scripts until they are required to decrease bytes consumed by network activity. Learn how to reduce unused JavaScript.LCPFCPUnscored
URL
Transfer Size
Est Savings
vercel.app 1st party
255.6 KiB	101.8 KiB
…chunks/10847b4a5b6101f0.js(sivarcasas.vercel.app)
185.4 KiB
79.0 KiB
…chunks/19deb65481cb608d.js(sivarcasas.vercel.app)
70.2 KiB
22.7 KiB



Missing source maps for large first-party JavaScript
Source maps translate minified code to the original source code. This helps developers debug in production. In addition, Lighthouse is able to provide further insights. Consider deploying source maps to take advantage of these benefits. Learn more about source maps.Unscored
URL
Map URL
vercel.app 1st party
…chunks/10847b4a5b6101f0.js(sivarcasas.vercel.app)
Large JavaScript file is missing a source map