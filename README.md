# Finanzas

App de escritorio (PWA para Chrome) que complementa a **Bluecoins** en Android: importa los movimientos que se descargan de los bancos, permite revisarlos y categorizarlos, controla que los saldos cuadren con el banco y prepara la exportación a Bluecoins.

**Dirección:** https://carlosmera10.github.io/finanzas-pc/

## Privacidad

- Este repositorio es **público** y solo contiene código.
- Los datos financieros se guardan **solo en el ordenador** (IndexedDB del navegador) y en las copias de seguridad que se descarguen desde **Ajustes → Exportar copia**.
- Los archivos reales de los bancos nunca se suben aquí. Las pruebas usan archivos **sintéticos** con datos inventados (`pruebas/sinteticos/`).

## Instalar la app

1. Abre la dirección en **Chrome** en el PC.
2. Pulsa **Instalar la app** en la parte inferior del menú lateral (o el icono de instalar de la barra de direcciones de Chrome).

## Qué hace (versión actual)

- **Cuentas:** alta con saldo de apertura, identificadores para reconocer sus archivos y nombre y tipo exactos en Bluecoins.
- **Categorías:** las mismas de Bluecoins (principal y subcategoría); se pueden pegar en lista.
- **Movimientos:** tabla con filtros, búsqueda (también por importe), selección múltiple, alta manual de gastos, ingresos y transferencias, y exportación del filtro a CSV para Excel.
- **Importar:** lee los archivos de la carpeta elegida o los que se arrastren: `.xlsx`, `.xls` de Excel 97-2003 (binario, con lector propio), `.xls` que en realidad son HTML o XML de Excel 2003, y `.csv`.
  - Importadores de **BBVA (cuenta y tarjetas)**, **ING (cuenta)** y **Trade Republic** (CSV), reconocidos por el contenido del archivo.
  - Revisión antes de confirmar: cuenta propuesta, nuevos frente a los que ya estaban (descargas que se solapan), saldo encadenado, saldo de apertura y avisos.
  - Transferencias entre cuentas propias y liquidaciones de tarjeta emparejadas automáticamente.
  - Control de saldo automático al importar y «Deshacer importación».
- **Historial de Bluecoins:** importa un archivo con todo lo apuntado en Bluecoins y lo cruza con lo importado del banco (completa los movimientos que coinciden, añade el resto como histórico y lista lo que solo está en Bluecoins). Con «Deshacer importación».
- **Reglas** de categorización (contiene / empieza por / expresión regular), con «Crear regla» desde un movimiento.
- **Etiquetas** con espacios y emojis (como en Bluecoins), con sugerencias de las existentes: en la importación (por fila o para todos los nuevos), automáticas por cuenta, en bloque, filtro por etiqueta y gestión (crear, renombrar, eliminar).
- **Controles de saldo:** comparan el saldo real del banco (y el de Bluecoins) con el de la app y proponen posibles causas si no cuadra.
- **Copias de seguridad:** exportar y restaurar un archivo con todos los datos, con recordatorio.
- Modo claro y oscuro, «Deshacer» en todos los cambios (también con Ctrl+Z) y atajos de teclado.

## Estructura

| Archivo | Para qué sirve |
|---|---|
| `index.html` | Toda la app (HTML, CSS y JavaScript sin librerías) |
| `sw.js` | Service worker: funciona sin conexión; cachés con prefijo `fin-` |
| `app.webmanifest`, `icon-*.png` | Instalación como app |
| `pruebas/generar_sinteticos.py` | Crea los archivos de prueba inventados |
| `pruebas/test_app.py` | Pruebas con Playwright (PC 1440×900 y ventana estrecha 361×780) |

Todo lo que guarda la app usa el prefijo `fin` (`fin_db`, `fin_ui`, `fin_tabs`), para no mezclarse con las demás apps de `carlosmera10.github.io`.

## Pruebas

```bash
python3 pruebas/generar_sinteticos.py
python3 -m http.server 8000 &
python3 pruebas/test_app.py
pkill -f "http.serve[r] 8000"
```
