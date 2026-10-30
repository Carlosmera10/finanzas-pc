"""Pruebas de la app con Playwright + Chromium sin interfaz.

Uso (desde la raíz del repositorio):
  python3 -m http.server 8000 &          # servir el repositorio
  python3 pruebas/test_app.py
  pkill -f "http.serve[r] 8000"          # pararlo
"""
import json
import os
import sys

from playwright.sync_api import sync_playwright

URL = "http://localhost:8000/"
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SINT = os.path.join(RAIZ, "pruebas", "sinteticos")
CAPT = os.path.join(RAIZ, "pruebas", "capturas")
os.makedirs(CAPT, exist_ok=True)

fallos = []


def ok(cond, msg):
    print(("  ✔ " if cond else "  ✖ ") + msg)
    if not cond:
        fallos.append(msg)


def nueva_pagina(browser, w, h, errores):
    ctx = browser.new_context(viewport={"width": w, "height": h}, accept_downloads=True, locale="es-ES", timezone_id="Europe/Madrid")
    ctx.route("**/fonts.googleapis.com/**", lambda r: r.abort())
    ctx.route("**/fonts.gstatic.com/**", lambda r: r.abort())
    p = ctx.new_page()
    # Se ignoran los avisos de la tipografía, que se bloquea a propósito
    p.on("console", lambda m: errores.append(m.text) if m.type == "error" and "fonts.g" not in (m.location or {}).get("url", "") else None)
    p.on("pageerror", lambda e: errores.append(str(e)))
    p.goto(URL)
    p.wait_for_function("window.__fin && window.__fin.ready()")
    return ctx, p


UNIT_JS = r'''
() => {
  const F = window.__fin, out = [];
  const eq = (a, b, msg) => out.push([JSON.stringify(a) === JSON.stringify(b), msg + ' → ' + JSON.stringify(a)]);
  // Importes a céntimos
  eq(F.parseAmount('-1.234,56 €'), -123456, 'importe español con miles y €');
  eq(F.parseAmount('1,234.56'), 123456, 'importe inglés');
  eq(F.parseAmount('12,5'), 1250, 'un decimal');
  eq(F.parseAmount('(12,00)'), -1200, 'paréntesis = negativo');
  eq(F.parseAmount('12,00-'), -1200, 'signo al final');
  eq(F.parseAmount('+5'), 500, 'signo más');
  eq(F.parseAmount('1.234'), 123400, '1.234 = mil doscientos');
  eq(F.parseAmount('0.5'), 50, '0.5');
  eq(F.parseAmount('1.234', {decimal: '.'}), 123, 'decimal punto explícito');
  eq(F.parseAmount(-45.67), -4567, 'número negativo');
  eq(F.parseAmount(0.1 + 0.2), 30, 'float 0.1+0.2');
  eq(F.parseAmount(1.005), 101, 'redondeo 1.005');
  eq(F.parseAmount('−3,10'), -310, 'signo menos unicode');
  eq(F.parseAmount('1 234,56'), 123456, 'espacio de miles');
  eq(F.parseAmount('abc'), null, 'texto no válido');
  eq(F.parseAmount(''), null, 'vacío');
  eq(F.parseAmount('-0,00'), 0, 'cero sin signo');
  eq(F.centsToPlain(-5), '-0.05', 'céntimos a texto');
  eq(F.centsToComma(123456), '1234,56', 'céntimos con coma');
  // Fechas
  eq(F.excelSerialToYMD(46266), '2026-09-01', 'número de serie de Excel');
  eq(F.parseDateCell('01/09/2026'), '2026-09-01', 'dd/mm/aaaa');
  eq(F.parseDateCell('1/9/26'), '2026-09-01', 'd/m/aa');
  eq(F.parseDateCell('2026-09-01T00:00:00.000'), '2026-09-01', 'ISO con hora');
  eq(F.parseDateCell('31/02/2026'), null, 'fecha imposible');
  eq(F.parseDateCell('20260901'), '2026-09-01', 'aaaammdd');
  eq(F.parseDateCell(46266), '2026-09-01', 'número');
  eq(F.addDays('2026-03-28', 2), '2026-03-30', 'sumar días con cambio de hora');
  eq(F.addDays('2026-12-31', 1), '2027-01-01', 'cambio de año');
  eq(F.daysBetween('2026-03-01', '2026-04-01'), 31, 'días entre fechas');
  // CSV
  eq(F.detectSep('a;b;c\n1;"2;3";4\n'), ';', 'detecta punto y coma');
  eq(F.detectSep('a,b,c\n1,2,3\n'), ',', 'detecta coma');
  eq(F.parseCsv('a;"b ""c""";d\r\n1;2;3\r\n', ';'), [['a', 'b "c"', 'd'], ['1', '2', '3']], 'comillas en CSV');
  // Textos y categorías
  eq(F.normText('  Cafetería   Plaza '), 'CAFETERIA PLAZA', 'normaliza concepto');
  eq(F.splitLabels('Tarjeta Ana💳, Playa 🌴; playa 🌴'), ['Tarjeta Ana💳', 'Playa 🌴'], 'etiquetas con espacios, emojis y sin repetir');
  eq(F.parseCatLines('Comida > Súper\nCasa;Luz\n\nOcio'), [{parent:'Comida',child:'Súper'},{parent:'Casa',child:'Luz'},{parent:'Ocio',child:null}], 'líneas de categorías');
  // CSV de Bluecoins
  eq(F.bluecoinsCsv([{type:'e',date:'01/09/2026',payee:'Café, bar',amount:'-1.80',parent:'Comida',category:'Cafés',accountType:'Bank',account:'Prueba',notes:'',labels:'',status:'',split:''}]),
     '(1)Type,(2)Date,(3)Item or Payee,(4)Amount,(5)Category Type,(6)Category,(7)Account Type,(8)Account,(9)Notes,(10) Label,(11) Status,(12) Split\r\ne,01/09/2026,"Café, bar",-1.80,Comida,Cafés,Bank,Prueba,,,,\r\n', 'CSV de Bluecoins');
  // RK de Excel 97-2003
  eq([F.rkValue(0x00000006), F.rkValue(310*4+3), F.rkValue((-5*4+2)>>>0)], [1, 3.1, -5], 'números RK');
  // Reglas
  const r = F.normRule({id:'r', text:'mercadona', mode:'contiene', set:{categoryId:'c'}});
  eq([F.ruleMatches(r, {rawConcept:'Pago en MERCADONA Madrid', amountCents:-100}), F.ruleMatches({...r, sign:'pos'}, {rawConcept:'MERCADONA', amountCents:-100}),
      F.ruleMatches({...r, mode:'empieza'}, {rawConcept:'Pago en MERCADONA', amountCents:-1})], [true, false, false], 'coincidencia de reglas');
  eq(F.suggestRuleText({rawConcept:'Adeudo de telefonica · Adeudo nº 2026295000547127'}), 'TELEFONICA', 'texto propuesto para la regla');
  eq(F.suggestRuleText({rawConcept:'Bizum · Enviado: cena amigos'}), 'ENVIADO: CENA AMIGOS', 'regla de un Bizum');
  return out;
}
'''

READERS_JS = r"""
async () => {
  const F = window.__fin, out = [];
  const eq = (a, b, msg) => out.push([JSON.stringify(a) === JSON.stringify(b), msg + ' → ' + JSON.stringify(a)]);
  const leer = async n => F.readSpreadsheetBytes(new Uint8Array(await (await fetch('pruebas/sinteticos/' + n)).arrayBuffer()));
  // xlsx real
  let r = await leer('sintetico-xlsx.xlsx');
  eq(r.format, 'xlsx', 'xlsx: formato');
  let rows = r.sheets[0].rows, h = rows.findIndex(x => x && x[0] && x[0].v === 'F. Operación');
  eq(h, 3, 'xlsx: fila de cabeceras');
  eq(rows[h + 1][0].t, 'd', 'xlsx: la fecha se reconoce como fecha');
  eq(F.parseDateCell(rows[h + 1][0].v), '2026-09-01', 'xlsx: valor de la fecha');
  eq(F.parseAmount(rows[h + 2][3].raw, {decimal: '.'}), -4567, 'xlsx: importe exacto');
  eq(rows[h + 3][2].v, 'PAGO CON TARJETA CAFETERÍA PLAZA', 'xlsx: texto con acentos');
  eq(r.sheets[0].name, 'Movimientos', 'xlsx: nombre de la hoja');
  // HTML disfrazado de .xls
  r = await leer('sintetico-html.xls');
  eq(r.format, 'html', 'html: formato');
  rows = r.sheets[0].rows;
  eq(rows[1].map(c => c && c.v), ['Fecha', 'Concepto', 'Importe'], 'html: cabeceras');
  eq(F.parseAmount(rows[9][2].v), -123456, 'html: importe con miles');
  // XML de Excel 2003
  r = await leer('sintetico-xml2003.xls');
  eq(r.format, 'xml2003', 'xml2003: formato');
  rows = r.sheets[0].rows;
  eq(F.parseDateCell(rows[1][0].v), '2026-09-01', 'xml2003: fecha');
  eq(F.parseAmount(rows[1][2].raw, {decimal: '.'}), 215000, 'xml2003: importe');
  // CSV Windows-1252
  r = await leer('sintetico-1252.csv');
  eq([r.format, r.encoding, r.sep], ['csv', 'Windows-1252', ';'], 'csv: formato, codificación y separador');
  eq(r.sheets[0].rows[3][1].v, 'PAGO CON TARJETA CAFETERÍA PLAZA', 'csv: acentos en Windows-1252');
  eq(F.parseAmount(r.sheets[0].rows[8][2].v), -123456, 'csv: importe');
  // Binario antiguo
  r = await F.readSpreadsheetBytes(new Uint8Array([0xD0,0xCF,0x11,0xE0,0xA1,0xB1,0x1A,0xE1,0,0]));
  eq([r.format, !!r.error], ['biff', true], 'biff dañado: se avisa');
  // .xls binario de Excel 97-2003 (como el de ING)
  r = await leer('ing-cuenta.xls');
  eq([r.format, r.error], ['biff', undefined], 'biff: formato');
  rows = r.sheets[0].rows;
  eq(rows[0][3].v, '0000 0000 0000 00009999', 'biff: texto');
  eq([rows[4][0].t, F.parseDateCell(rows[4][0].v)], ['d', '2026-10-03'], 'biff: fecha');
  eq([F.parseAmount(rows[4][5].raw, {decimal:'.'}), F.parseAmount(rows[5][5].raw, {decimal:'.'})], [310, -6025], 'biff: importes');
  eq(rows[3].map(c => c && c.v).slice(0, 4), ['F. VALOR', 'CATEGORÍA', 'SUBCATEGORÍA', 'DESCRIPCIÓN'], 'biff: cabeceras con acentos');
  // Importadores
  const an = async n => F.analyzeFile({sheets: (await leer(n)).sheets});
  let a = await an('bbva-cuenta-septiembre.xlsx');
  eq([a.importerId, a.rows.length, a.from, a.to, a.chain.breaks.length, a.chain.opening, a.chain.closing], ['bbva_cuenta', 7, '2026-09-01', '2026-09-30', 0, 431530, 500000], 'BBVA cuenta: lectura y saldo encadenado');
  eq([a.rows[3].date, a.rows[3].valueDate, a.rows[3].rawConcept], ['2026-09-28', '2026-09-27', 'Bizum · Enviado: cena amigos'], 'BBVA cuenta: fecha, fecha valor y concepto');
  eq(a.rows.filter(x => x.settlementCard).length, 1, 'BBVA cuenta: detecta la liquidación de la tarjeta');
  a = await an('bbva-tarjeta.xlsx');
  eq([a.importerId, a.rows.length, a.ident.slice(-4), a.rows.filter(x => x.cardReceipt).length], ['bbva_tarjeta', 5, '1111', 1], 'BBVA tarjeta: lectura, tarjeta y recibo');
  a = await an('ing-cuenta.xls');
  eq([a.importerId, a.rows.length, a.ident.slice(-4), a.chain.breaks.length, a.rows[0].bankCategory], ['ing_cuenta', 4, '9999', 0, 'Ventajas ING › Otras Ventajas ING'], 'ING: lectura, cuenta y categoría del banco');
  a = await an('trade-republic.csv');
  eq([a.importerId, a.rows.length, a.rows[2].amountCents, a.rows[1].counterIban.slice(-4), !!a.rows[0].bankRef], ['tr_cuenta', 4, 810, '9999', true], 'Trade Republic: lectura, neto e IBAN');
  a = await an('sintetico-xlsx.xlsx');
  eq(a, null, 'un archivo de otro formato no se confunde con un banco');
  return out;
}
"""


def informe(resultados, titulo):
    print(titulo)
    for bien, msg in resultados:
        ok(bien, msg)


def sin_desborde(p, nombre):
    ancho = p.evaluate("() => [document.documentElement.scrollWidth, window.innerWidth]")
    ok(ancho[0] <= ancho[1], f"{nombre}: sin desborde horizontal ({ancho[0]} ≤ {ancho[1]})")


def flujo_pc(browser):
    errores = []
    ctx, p = nueva_pagina(browser, 1440, 900, errores)
    informe(p.evaluate(UNIT_JS), "Pruebas unitarias")
    informe(p.evaluate(READERS_JS), "Lectores de archivos")

    print("Flujo en el PC")
    # Cuentas
    p.click("text=Añadir cuenta")
    p.fill("#accName", "Cuenta A")
    p.fill("#accOpening", "1.000,00")
    p.fill("#accOpeningDate", "2026-08-31")
    p.fill("#accBcName", "Cuenta A")
    p.click("#accForm button[type=submit]")
    p.wait_for_selector("text=Cuenta añadida")
    p.click(".nav-btn[data-view=cuentas]")
    p.click("[data-act=new-acc]")
    p.fill("#accName", "Ahorro B")
    p.select_option("#accKind", "ahorro")
    p.fill("#accOpeningDate", "2026-08-31")
    p.click("#accForm button[type=submit]")
    ok(p.locator("tr[data-edit-acc]").count() == 2, "dos cuentas creadas")

    # Categorías pegadas
    p.click(".nav-btn[data-view=categorias]")
    p.click("[data-act=paste-cats] >> nth=0")
    p.fill("#txtBody textarea", "Comida > Supermercado\nComida > Cafés\nCasa > Luz")
    p.click("#txtOk")
    p.wait_for_selector("text=5 categorías añadidas")
    ok(p.locator(".cat-list li.child").count() == 3, "subcategorías pegadas")

    # Gasto manual
    p.keyboard.press("n")
    p.wait_for_selector("#movDlg[open]")
    p.fill("#movDate", "2026-09-02")
    p.fill("#movAmount", "45,67")
    p.select_option("#movCat", label="Supermercado")
    p.fill("#movConcept", "Compra semanal")
    p.click(".tags[data-tags=mov] .tag-in")
    p.keyboard.type("casa"); p.keyboard.press("Enter")
    p.keyboard.type("fin de semana 🏖"); p.keyboard.press("Enter")
    p.click("#movForm button[type=submit]")
    p.wait_for_selector("text=Movimiento añadido")
    ok(p.evaluate("() => [...window.__fin.S.movements.values()][0].labels") == ["casa", "fin de semana 🏖"], "etiquetas con espacios y emojis")

    # Transferencia manual
    p.click(".nav-btn[data-view=movimientos]")
    p.click("[data-act=new-mov] >> nth=0")
    p.click("#movKind button[data-kind=transferencia]")
    p.fill("#movDate", "2026-09-15")
    p.fill("#movAmount", "500")
    p.select_option("#movOther", label="Ahorro B")
    p.click("#movForm button[type=submit]")
    p.wait_for_selector("text=Transferencia añadida")
    ok(p.locator("tr[data-mov]").count() == 3, "tabla con 3 movimientos (gasto + transferencia en dos cuentas)")
    tot = p.inner_text(".totals")
    ok("45,67" in tot and "3 movimientos" in tot, "totales del filtro: " + tot.replace("\n", " "))

    # Búsqueda por importe
    p.fill("#movSearch", "45,67")
    p.wait_for_timeout(350)
    ok(p.locator("tr[data-mov]").count() == 1, "buscar por importe")
    p.click("[data-act=clear-filters]")

    # Deshacer con Ctrl+Z
    p.click("body")
    p.keyboard.press("Control+z")
    p.wait_for_timeout(300)
    ok(p.locator("tr[data-mov]").count() == 1, "Ctrl+Z deshace la transferencia (sus dos filas)")

    # Resumen: saldo
    p.click(".nav-btn[data-view=resumen]")
    txt = p.inner_text("#view").replace("\xa0", " ")
    ok("954,33" in txt, "saldo de la cuenta A = 1.000,00 − 45,67")
    ok("1.954,33" not in txt and "954,33 €" in txt, "formato español del saldo")

    # Control de saldo con descuadre
    p.click(".nav-btn[data-view=controles]")
    p.click("[data-act=new-check] >> nth=0")
    p.select_option("#chkAcc", label="Cuenta A")
    p.fill("#chkDate", "2026-09-30")
    p.fill("#chkReal", "950,00")
    ok("4,33" in p.inner_text("#chkCalc"), "el diálogo muestra la diferencia en vivo")
    p.click("#chkForm button[type=submit]")
    p.wait_for_selector("text=descuadre de 4,33")
    p.click("[data-act=toggle-causes]")
    ok("movimientos manuales" in p.inner_text("#view"), "propone causas del descuadre")
    p.click("[data-act=cause][data-state=manual]")
    ok(p.locator("tr[data-mov]").count() == 1, "la causa lleva a los movimientos filtrados")
    p.screenshot(path=os.path.join(CAPT, "pc-movimientos.png"))

    # Importar: lectura y vista previa
    p.click(".nav-btn[data-view=importar]")
    p.set_input_files("#fileInput", [os.path.join(SINT, n) for n in sorted(os.listdir(SINT)) if n.startswith("sintetico")])
    p.wait_for_selector(".file-item >> nth=3")
    ok(p.locator(".file-item").count() == 4, "cuatro archivos leídos")
    ok(p.locator(".file-item .chip.bad").count() == 0, "ninguno da error de lectura")
    ok(p.locator(".prev-tbl tbody tr").count() > 5, "vista previa con filas")
    p.screenshot(path=os.path.join(CAPT, "pc-importar.png"))

    # Copia de seguridad: exportar, borrar algo, restaurar
    p.click(".nav-btn[data-view=ajustes]")
    with p.expect_download() as d:
        p.click("[data-act=backup]")
    ruta = os.path.join(CAPT, "copia.json")
    d.value.save_as(ruta)
    copia = json.load(open(ruta, encoding="utf-8"))
    ok(copia["app"] == "finanzas-pc" and len(copia["stores"]["movements"]) == 1, "la copia contiene los datos")
    p.evaluate("() => window.__fin.commit('x', cs => { for (const k of [...window.__fin.S.movements.keys()]) cs.del('movements', k); })")
    ok(p.evaluate("() => window.__fin.S.movements.size") == 0, "movimientos borrados antes de restaurar")
    p.set_input_files("#restoreInput", ruta)
    p.click("#cfmOk")
    p.wait_for_selector("text=Copia restaurada")
    ok(p.evaluate("() => window.__fin.S.movements.size") == 1, "la copia restaura los movimientos")
    os.remove(ruta)

    # Persistencia tras recargar
    p.reload()
    p.wait_for_function("window.__fin && window.__fin.ready()")
    ok(p.evaluate("() => [window.__fin.S.accounts.size, window.__fin.S.movements.size, window.__fin.S.checks.size]") == [2, 1, 1], "los datos siguen tras recargar")

    # Tema oscuro sin errores
    p.click(".nav-btn[data-view=ajustes]")
    p.click("#themeSeg button[data-theme=dark]")
    ok(p.evaluate("() => document.documentElement.dataset.theme") == "dark", "tema oscuro")
    p.click(".nav-btn[data-view=resumen]")
    p.screenshot(path=os.path.join(CAPT, "pc-resumen-oscuro.png"))
    p.reload()
    ok(p.evaluate("() => document.documentElement.dataset.theme") == "dark", "el tema se aplica al abrir (sin parpadeo)")

    for v in ["resumen", "estadisticas", "balance", "presupuestos", "movimientos", "importar", "controles", "cuentas", "categorias", "reglas", "ajustes", "instrucciones"]:
        p.click(f".nav-btn[data-view={v}]")
        sin_desborde(p, "PC " + v)
    ok(not errores, "sin errores en la consola (PC): " + "; ".join(errores[:3]))
    estado = p.evaluate("() => window.__fin.backupData()")
    ctx.close()
    return estado


def importar(p, nombre):
    p.set_input_files("#fileInput", os.path.join(SINT, nombre))
    p.wait_for_selector(f".file-item[aria-current=true] >> text={nombre}")


def flujo_importacion(browser):
    errores = []
    ctx, p = nueva_pagina(browser, 1440, 900, errores)
    print("Importación de bancos")
    p.click(".nav-btn[data-view=importar]")
    # BBVA septiembre: la cuenta se crea desde la revisión
    importar(p, "bbva-cuenta-septiembre.xlsx")
    ok(p.is_disabled("[data-act=rv-confirm]"), "sin cuenta no se puede confirmar")
    p.click("[data-act=rv-new-acc]")
    ok(p.input_value("#accName") == "BBVA" and p.input_value("#accBank") == "bbva", "la cuenta nueva viene rellenada")
    p.click("#accForm button[type=submit]")
    p.wait_for_function("document.querySelector('#rvAcc') && document.querySelector('#rvAcc').value !== ''")
    ok(p.is_checked("#rvOpening"), "propone el saldo de apertura deducido del archivo")
    p.screenshot(path=os.path.join(CAPT, "pc-revision.png"))
    p.click("[data-act=rv-confirm]")
    p.wait_for_selector("text=7 movimientos importados en BBVA · el saldo cuadra")
    ok(True, "BBVA septiembre importado y el saldo cuadra")
    # BBVA octubre: se solapa con septiembre
    importar(p, "bbva-cuenta-octubre.xlsx")
    txt = p.inner_text("#view")
    ok("2 nuevos" in txt and "3 ya estaban" in txt, "detecta los solapados (2 nuevos, 3 ya estaban)")
    p.click("[data-act=rv-confirm]")
    p.wait_for_selector("text=2 movimientos importados en BBVA · el saldo cuadra")
    ok(True, "BBVA octubre sin duplicados y el saldo cuadra")
    # Tarjeta: cuenta nueva vinculada a BBVA; el recibo se empareja con la liquidación
    importar(p, "bbva-tarjeta.xlsx")
    p.click("[data-act=rv-new-acc]")
    ok(p.input_value("#accHints") == "1111" and p.input_value("#accKind") == "tarjeta_credito", "la tarjeta viene con sus 4 dígitos")
    p.click(".tags[data-tags=acc] .tag-in")
    p.keyboard.type("Tarjeta Ana💳"); p.keyboard.press("Enter")
    p.click("#accForm button[type=submit]")
    p.wait_for_selector("text=5 nuevos")
    # Etiqueta para todos los nuevos y etiqueta de una fila eligiendo una sugerencia
    p.click(".tags[data-tags=rv-all] .tag-in")
    p.keyboard.type("Viaje prueba"); p.keyboard.press("Enter")
    p.wait_for_selector(".tags[data-tags=rv-all] .tag")
    p.click(".rv-tbl .tags .tag-in >> nth=0")
    p.keyboard.type("Cafés"); p.keyboard.press("Enter")
    p.click("[data-act=rv-confirm]")
    p.wait_for_selector("text=5 movimientos importados")
    et = p.evaluate("""() => { const ms = [...window.__fin.S.movements.values()].filter(m => window.__fin.S.accounts.get(m.accountId).kind === 'tarjeta_credito');
      return {compras: ms.filter(m => m.kind === 'gasto').map(m => m.labels), recibo: ms.find(m => m.kind === 'transferencia').labels}; }""")
    ok(all("Tarjeta Ana💳" in l and "Viaje prueba" in l for l in et["compras"]), "las compras llevan la etiqueta de la tarjeta y la de todos los nuevos")
    ok(any("Cafés" in l for l in et["compras"]), "etiqueta añadida en una fila de la revisión")
    ok("Tarjeta Ana💳" not in et["recibo"], "la liquidación no lleva etiquetas de compra")
    estado = p.evaluate("""() => { const S = window.__fin.S, ms = [...S.movements.values()];
      const liq = ms.filter(m => m.kind === 'transferencia' && Math.abs(m.amountCents) === 5530);
      const cafes = ms.filter(m => m.rawConcept === 'Cafeteria plaza').length;
      return {pares: liq.length === 2 && liq[0].transferPairId && liq[0].transferPairId === liq[1].transferPairId, cafes}; }""")
    ok(estado["pares"], "la liquidación de la tarjeta queda emparejada (cuenta ↔ tarjeta)")
    ok(estado["cafes"] == 2, "dos cafés iguales el mismo día se mantienen los dos")
    # Tarjeta con cargo mensual: su saldo es lo pendiente de cargar y la cuenta tiene «disponible real»
    tj = p.evaluate("""() => { const F = window.__fin, S = F.S, t = [...S.accounts.values()].find(a => a.kind === 'tarjeta_credito'), b = [...S.accounts.values()].find(a => a.name === 'BBVA');
      return [F.balanceAt(t.id, '2026-09-03'), F.balanceAt(t.id, '2026-09-30'), F.cardInfo(t.id, '2026-09-30').month, F.availableAt(b.id, '2026-09-30') - F.balanceAt(b.id, '2026-09-30')]; }""")
    ok(tj == [-5530, -1600, -1600, -1600], f"tarjeta: antes del recibo debe agosto; después, solo lo de septiembre; disponible real = saldo − tarjeta → {tj}")
    p.click(".nav-btn[data-view=cuentas]")
    p.click("tr:has-text('Tarjeta BBVA') [data-edit-acc]")
    ok(p.is_visible("#accLimit") and p.is_hidden("#accOpening"), "las tarjetas tienen límite y no saldo de apertura")
    p.fill("#accLimit", "20")
    p.click("#accForm button[type=submit]")
    p.wait_for_selector("text=Cuenta guardada")
    p.click(".nav-btn[data-view=importar]")
    # ING: .xls binario; la transferencia de BBVA se empareja
    importar(p, "ing-cuenta.xls")
    p.click("[data-act=rv-new-acc]")
    p.click("#accForm button[type=submit]")
    p.wait_for_selector("text=4 nuevos")
    ok("Se empareja con un movimiento de BBVA" in p.inner_text("#view"), "la revisión anuncia la transferencia con BBVA")
    p.click("[data-act=rv-confirm]")
    p.wait_for_selector("text=4 movimientos importados en ING · el saldo cuadra")
    par = p.evaluate("""() => { const ms = [...window.__fin.S.movements.values()].filter(m => Math.abs(m.amountCents) === 100000);
      return ms.length === 2 && ms.every(m => m.kind === 'transferencia') && ms[0].transferPairId === ms[1].transferPairId; }""")
    ok(par, "transferencia BBVA → ING emparejada")
    # Trade Republic: CSV sin saldo; intereses netos; transferencia reconocida por el IBAN
    importar(p, "trade-republic.csv")
    p.click("[data-act=rv-new-acc]")
    ok(p.input_value("#accBank") == "tr", "la cuenta nueva es de Trade Republic")
    p.click("#accForm button[type=submit]")
    p.wait_for_selector("text=4 nuevos")
    ok(p.is_checked("#rvOpening") and "0,00" in p.inner_text(".rv-opts"), "propone saldo de apertura 0 (el archivo trae todo el historial)")
    p.click("[data-act=rv-confirm]")
    p.wait_for_selector("text=4 movimientos importados en Trade Republic")
    tr = p.evaluate("""() => { const F = window.__fin, S = F.S, a = [...S.accounts.values()].find(x => x.bank === 'tr');
      const ms = [...S.movements.values()].filter(m => m.accountId === a.id).sort((x, y) => x.date.localeCompare(y.date));
      const ing = [...S.accounts.values()].find(x => x.bank === 'ing');
      return {importes: ms.map(m => m.amountCents), fechas: ms.map(m => m.date), saldo: F.balanceAt(a.id, '2026-12-31'),
        transf: ms.filter(m => m.kind === 'transferencia').map(m => m.transferAccountId === ing.id)}; }""")
    ok(tr["importes"] == [200000, -30000, 810, 972], f"intereses netos de retención {tr['importes']}")
    ok(tr["fechas"][-1] == "2026-10-01", "la hora UTC se pasa a la fecha de Madrid")
    ok(tr["saldo"] == 200000 - 30000 + 810 + 972, "saldo de Trade Republic")
    ok(tr["transf"] == [True], "el IBAN de ING convierte el movimiento en transferencia a ING")
    p.evaluate("() => { window.__fin.imp.files = []; }")
    importar(p, "trade-republic.csv")
    ok("0 nuevos" in p.inner_text("#view"), "Trade Republic: reimportar no duplica (identificador único)")
    # Volver a importar lo mismo no duplica nada
    n = p.evaluate("() => window.__fin.S.movements.size")
    p.evaluate("() => { window.__fin.imp.files = []; }")
    importar(p, "bbva-cuenta-septiembre.xlsx")
    ok("0 nuevos" in p.inner_text("#view") and "Este archivo ya se importó" in p.inner_text("#view"), "reimportar el mismo archivo: 0 nuevos")
    ok(p.evaluate("() => window.__fin.S.movements.size") == n, "no se ha añadido nada")
    # Filtro por etiqueta y quitar una etiqueta en bloque
    p.click(".nav-btn[data-view=movimientos]")
    p.select_option(".f-label", "Viaje prueba")
    n_viaje = p.locator("tr[data-mov]").count()
    ok(n_viaje == 4, f"filtro por etiqueta ({n_viaje})")
    p.check("#selPage")
    p.click(".tags[data-tags=bulk] .tag-in"); p.keyboard.type("viaje")
    p.wait_for_selector(".tag-opt.on >> text=Viaje prueba")
    ok(True, "sugiere las etiquetas que ya existen")
    p.keyboard.press("Enter")
    ok(p.inner_text(".tags[data-tags=bulk] .tag") == "Viaje prueba", "elige la sugerencia con Intro (respeta mayúsculas)")
    p.click("[data-act=bulk-tag-del]")
    p.wait_for_selector("text=Etiquetas quitadas de 4 movimientos")
    ok(p.locator("tr[data-mov]").count() == 0, "etiqueta quitada en bloque")
    p.click("[data-act=clear-filters]")
    if p.locator("[data-act=sel-none]").count(): p.click("[data-act=sel-none]")
    # Crear una regla desde un movimiento
    p.evaluate("() => window.__fin.commit('', cs => { cs.put('categories', {id:'p1', parent:null, name:'Compras', kind:'gasto'}); cs.put('categories', {id:'c1', parent:'p1', name:'Supermercado', kind:'gasto'}); }, {noUndo:true})")
    p.click(".nav-btn[data-view=movimientos]")
    p.fill("#movSearch", "mercadona")
    p.wait_for_timeout(300)
    p.click("tr[data-mov]")
    p.click("#movRule")
    p.wait_for_selector("#ruleDlg[open]")
    ok(p.input_value("#ruleText") == "MERCADONA C. MA", "la regla propone el texto del concepto")
    p.select_option("#ruleCat", "c1")
    p.fill("#rulePayee", "Mercadona")
    p.click("#ruleForm button[type=submit]")
    p.wait_for_selector("text=Regla creada y aplicada a 1 movimientos")
    ok(True, "regla creada y aplicada")
    # Deshacer la importación de ING: la transferencia de BBVA vuelve a como estaba
    p.click(".nav-btn[data-view=importar]")
    p.click("tr:has-text('ing-cuenta.xls') [data-act=undo-import]")
    p.click("#cfmOk")
    p.wait_for_selector("text=Importación deshecha")
    vuelta = p.evaluate("""() => { const m = [...window.__fin.S.movements.values()].find(m => m.amountCents === -100000); return [m.kind, m.transferPairId]; }""")
    ok(vuelta == ["gasto", None], "al deshacer, la transferencia de BBVA vuelve a ser como antes")
    # Historial de Bluecoins: se cruza con lo importado del banco
    saldo_bbva = p.evaluate("() => { const F = window.__fin, a = [...F.S.accounts.values()].find(x => x.name === 'BBVA'); return F.balanceAt(a.id, '2026-12-31'); }")
    importar(p, "bluecoins-historial.json")
    txt = p.inner_text("#view")
    ok("Coinciden con el banco\n2" in txt and "Se añaden como histórico\n5" in txt, "historial: 2 coinciden y 5 se añaden")
    ok("Billetera" in txt and "Hipoteca ficticia" in txt, "propone las cuentas nuevas")
    ok("1 movimientos de Bluecoins caen en fechas" in txt, "avisa del que solo está en Bluecoins")
    p.click("[data-act=bc-confirm]")
    p.wait_for_selector("text=Historial importado")
    h = p.evaluate("""() => { const F = window.__fin, S = F.S, ms = [...S.movements.values()], acc = n => [...S.accounts.values()].find(a => a.name === n);
      const col = ms.find(m => m.rawConcept.startsWith('Adeudo colegio') && m.bcRef);
      const div = ms.find(m => m.rawConcept === 'Mercadona c. ma');
      const tr = ms.filter(m => m.source === 'bluecoins' && m.kind === 'transferencia');
      return {bbva: F.balanceAt(acc('BBVA').id, '2026-12-31'), billetera: F.balanceAt(acc('Billetera').id, '2026-12-31'),
        hipoteca: [F.balanceAt(acc('Hipoteca ficticia').id, '2026-12-31'), acc('Hipoteca ficticia').inStats],
        colegio: col && [col.payee, F.catLabel(col.categoryId), col.labels.includes('Cole 🎒'), col.exportId],
        dividido: div && [div.bcRef.split(',').length, div.notes.includes('Dividido en Bluecoins')],
        pareja: tr.length === 2 && tr[0].transferPairId && tr[0].transferPairId === tr[1].transferPairId,
        flujos: [F.flowsBetween('2024-01-01', '2024-12-31'), F.flowsBetween('2025-01-01', '2025-12-31')].map(f => [f.inc, f.exp]),
        historicos: ms.filter(m => m.historic).length}; }""")
    ok(h["bbva"] == saldo_bbva, "el saldo de BBVA (con banco) no cambia")
    ok(h["billetera"] == 150000, "Billetera: saldo como en Bluecoins")
    ok(h["hipoteca"] == [5010000, False], "la hipoteca no cuenta en ingresos y gastos")
    ok(h["colegio"] == ["Colegio", "Salud › Colegio", True, "bluecoins"], f"el movimiento del banco se completa con Bluecoins {h['colegio']}")
    ok(h["dividido"] == [2, True], "la compra dividida en Bluecoins se reconoce por la suma")
    ok(h["pareja"], "las dos partes de una transferencia de Bluecoins quedan emparejadas")
    ok(h["flujos"] == [[0, 50000], [0, 2500]], f"estadísticas con el histórico {h['flujos']}")
    ok(h["historicos"] == 2, "lo de BBVA anterior al banco queda como histórico (no cuenta en el saldo)")
    p.click("tr:has-text('bluecoins-historial') [data-act=undo-import]")
    p.click("#cfmOk")
    p.wait_for_selector("text=Importación del historial deshecha")
    ok(p.evaluate("() => [...window.__fin.S.movements.values()].filter(m => m.bcRef || m.source === 'bluecoins').length + [...window.__fin.S.accounts.values()].filter(a => a.name === 'Billetera').length") == 0, "deshacer el historial lo quita todo")
    sin_desborde(p, "PC importar")
    ok(not errores, "sin errores en la consola (importación): " + "; ".join(errores[:3]))
    ctx.close()


def flujo_estrecho(browser, estado):
    errores = []
    ctx, p = nueva_pagina(browser, 361, 780, errores)
    print("Ventana estrecha")
    # Cargar los mismos datos para ver las vistas llenas
    p.evaluate("""(d) => window.__fin.commit('', cs => { for (const s of Object.keys(d.stores)) for (const r of d.stores[s]) cs.put(s, r); }, {noUndo:true})""", estado)
    for v in ["resumen", "estadisticas", "balance", "presupuestos", "movimientos", "importar", "controles", "cuentas", "categorias", "reglas", "ajustes", "instrucciones"]:
        p.click("#menuBtn")
        p.click(f".nav-btn[data-view={v}]")
        p.wait_for_timeout(250)
        sin_desborde(p, "Estrecha " + v)
        if v in ("resumen", "estadisticas", "balance", "presupuestos", "movimientos", "controles"):
            p.screenshot(path=os.path.join(CAPT, f"movil-{v}.png"), full_page=True)
    p.keyboard.press("n")
    p.wait_for_selector("#movDlg[open]")
    caja = p.evaluate("() => { const r = document.querySelector('#movDlg').getBoundingClientRect(); return [r.left, r.right, innerWidth]; }")
    ok(caja[0] >= 0 and caja[1] <= caja[2], "el diálogo cabe en la pantalla")
    p.screenshot(path=os.path.join(CAPT, "movil-dialogo.png"))
    ok(not errores, "sin errores en la consola (estrecha): " + "; ".join(errores[:3]))
    ctx.close()

# Datos inventados para las estadísticas: 24 meses completos y lo que va del mes actual.
# Cuenta A (corriente) con apertura hace 6 meses (lo anterior es histórico), Cuenta B (ahorro)
# e Hipoteca (no cuenta en ingresos y gastos).
SEMILLA_STATS_JS = r"""
() => {
  const F = window.__fin, today = F.ymd(new Date()), ym0 = today.slice(0, 7);
  const ymAdd = (ym, n) => { const d = new Date(+ym.slice(0, 4), +ym.slice(5, 7) - 1 + n, 1); return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0'); };
  const open = ymAdd(ym0, -6) + '-01';
  const acc = [
    {id: 'A', name: 'Cuenta A', kind: 'corriente', openingCents: 500000, openingDate: open, order: 1},
    {id: 'B', name: 'Ahorro B', kind: 'ahorro', openingCents: 100000, openingDate: ymAdd(ym0, -24) + '-01', order: 2},
    {id: 'H', name: 'Hipoteca', kind: 'prestamo', openingCents: -9000000, openingDate: ymAdd(ym0, -24) + '-01', inStats: false, order: 3},
  ].map(F.normAccount);
  const cat = [
    {id: 'casa', name: 'Casa'}, {id: 'alq', name: 'Alquiler', parent: 'casa'}, {id: 'luz', name: 'Luz', parent: 'casa'},
    {id: 'comida', name: 'Comida'}, {id: 'super', name: 'Supermercado', parent: 'comida'},
    {id: 'ocio', name: 'Ocio'}, {id: 'cine', name: 'Cine', parent: 'ocio'},
    {id: 'ing', name: 'Ingresos', kind: 'ingreso'}, {id: 'nom', name: 'Nómina', parent: 'ing', kind: 'ingreso'},
  ].map(F.normCategory);
  const movs = []; let n = 0;
  const add = (accountId, date, amountCents, kind, categoryId, payee, extra = {}) => {
    if (date > today) return;
    movs.push(F.normMovement(Object.assign({id: 'm' + (++n), accountId, date, amountCents, kind, categoryId, payee, concept: payee,
      historic: accountId === 'A' && date < open, source: accountId === 'A' && date < open ? 'bluecoins' : 'manual', reviewed: true}, extra)));
  };
  for (let k = -24; k <= 0; k++) {
    const ym = ymAdd(ym0, k);
    add('A', ym + '-01', 200000, 'ingreso', 'nom', 'Empresa');
    add('A', ym + '-03', -70000, 'gasto', 'alq', 'Casero');
    add('A', ym + '-10', -30000, 'gasto', 'super', 'Super X');
    add('A', ym + '-15', k === -1 ? -40000 : -10000, 'gasto', 'cine', 'Cines', k === -1 ? {labels: ['Viaje']} : {});
    add('A', ym + '-18', k === -1 ? -8000 : -5000, 'gasto', 'luz', 'Eléctrica');
    add('A', ym + '-20', -50000, 'transferencia', null, 'A ahorro', {transferAccountId: 'B'});
    add('B', ym + '-20', 50000, 'transferencia', null, 'Desde A', {transferAccountId: 'A'});
    add('H', ym + '-05', 30000, 'ingreso', 'nom', 'Ajuste');
  }
  return F.commit('', cs => { for (const a of acc) cs.put('accounts', a); for (const c of cat) cs.put('categories', c); for (const m of movs) cs.put('movements', m); }, {noUndo: true}).then(() => ({n: movs.length, open}));
}
"""


def flujo_estadisticas(browser):
    errores = []
    ctx, p = nueva_pagina(browser, 1440, 900, errores)
    print("Estadísticas, balance y presupuestos")
    sem = p.evaluate(SEMILLA_STATS_JS)
    ok(sem["n"] > 150, f"datos de prueba cargados ({sem['n']} movimientos)")
    F = "window.__fin"
    # Motor: el mes anterior completo, con las cuentas predeterminadas (sin la hipoteca)
    r = p.evaluate(f"""() => {{ const F={F}, [f,t]=F.periodRange('mesant'), d=F.scopeIds('stats',null);
      const T=F.totals(F.flows(d).filter(x=>x.d>=f&&x.d<=t));
      return [[...d].sort(), T.inc, T.exp, T.save]; }}""")
    ok(r[0] == ["A", "B"], "por defecto no se suma la hipoteca en ingresos y gastos")
    ok(r[1:] == [200000, 148000, 52000], f"mes anterior: ingresos 2.000, gastos 1.480, ahorro 520 → {r[1:]}")
    # Saldo hacia atrás antes de la apertura (con el histórico)
    r = p.evaluate(f"""() => {{ const F={F}, a=F.S.accounts.get('A'), d=F.addDays(a.openingDate,-1);
      return [F.balanceHist(a,d), F.balanceHist(a,F.addDays(a.openingDate,-40))]; }}""")
    ok(r[0] == 500000, "el día antes de la apertura el saldo es el de apertura")
    ok(r[1] != 500000, f"antes se reconstruye con el histórico ({r[1]})")
    # Avisos
    ins = p.evaluate(f"() => {F}.insightsFor({F}.scopeIds('stats',null)).map(x=>x.text)")
    ok(any("Ocio" in t and "más que su media" in t for t in ins), "aviso: Ocio se disparó el mes pasado")
    ok(any("Eléctrica ha subido" in t for t in ins), "aviso: recibo que sube")

    # Estadísticas en pantalla
    p.click(".nav-btn[data-view=estadisticas]")
    p.select_option("[data-st=period]", "mesant")
    p.wait_for_timeout(200)
    txt = p.inner_text("#view").replace("\xa0", " ")
    ok("1.480,00 €" in txt and "2.000,00 €" in txt, "las cifras del periodo aparecen en pantalla")
    ok(p.locator(".viz svg").count() >= 6, f"gráficos dibujados ({p.locator('.viz svg').count()})")
    # Tooltip al pasar por un gráfico
    p.hover(".vcard:has-text('Ingresos y gastos por mes') rect.hit >> nth=0")
    ok(p.is_visible("#vizTip") and "Ingresos" in p.inner_text("#vizTip"), "tooltip al pasar el ratón")
    # Ver como tabla
    p.click(".vcard:has-text('Ingresos y gastos por mes') details.vtable summary")
    ok(p.locator(".vcard:has-text('Ingresos y gastos por mes') details.vtable tbody tr").count() >= 1, "vista de tabla del gráfico")
    # Desglose de una categoría
    p.click("tr[data-st-cat=ocio]")
    ok(p.locator("tr.subrow").count() == 1 and p.locator(".vcard:has-text('Últimos 24 meses')").count() == 1, "pulsar una categoría abre sus subcategorías y su evolución")
    p.screenshot(path=os.path.join(CAPT, "pc-estadisticas.png"), full_page=True)

    # Cuentas de un elemento: solo «Ahorro B» en el resumen del periodo
    p.click(".vcard:has-text('Resumen del periodo') .scope-chip")
    p.wait_for_selector("#scopeDlg[open]")
    p.uncheck("#scopeInheritChk")
    p.click("[data-scope-all='0']")
    p.check("input[data-scope-acc=B]")
    p.fill("#scopeSetName", "Solo ahorro")
    p.click("#scopeSaveSet")
    p.click("#scopeForm button[type=submit]")
    p.wait_for_timeout(200)
    kpi = p.inner_text(".vcard:has-text('Resumen del periodo')").replace("\xa0", " ")
    ok("Solo ahorro" in kpi and "0,00 €" in kpi, "el elemento usa sus propias cuentas (conjunto «Solo ahorro»)")
    ok("Traspasos con otras cuentas" in kpi, "muestra los traspasos con cuentas fuera de la selección")
    otro = p.inner_text(".vcard:has-text('Ingresos y gastos por mes') .scope-chip")
    ok("Solo ahorro" not in otro, "los demás elementos siguen con las cuentas de la página")
    # Cuentas de la página: incluir la hipoteca
    p.click("#topActions .scope-chip")
    p.wait_for_selector("#scopeDlg[open]")
    ok(p.is_hidden("#scopeInherit"), "en la página no aparece «Las mismas que la página»")
    p.click("[data-scope-all='1']")
    p.click("#scopeForm button[type=submit]")
    p.wait_for_timeout(200)
    r = p.evaluate(f"() => [...{F}.scopeIds('stats','stats.evol')].sort()")
    ok(r == ["A", "B", "H"], "la página puede sumar también la hipoteca")
    # Volver a lo predeterminado
    p.click("#topActions .scope-chip")
    p.click("#scopeReset")
    p.wait_for_timeout(150)
    ok(p.evaluate(f"() => [...{F}.scopeIds('stats','stats.evol')].sort()") == ["A", "B"], "«Volver a lo predeterminado»")

    # Balance
    p.click(".nav-btn[data-view=balance]")
    p.wait_for_selector(".vcard:has-text('Evolución del patrimonio') svg")
    ok("aproximado" in p.inner_text("#view"), "avisa de que el saldo anterior a la apertura es aproximado")
    p.click("[data-bal-mode=cuentas]")
    ok(p.locator(".vcard:has-text('Evolución del patrimonio') .legend .lg").count() == 3, "evolución por cuenta con leyenda")
    p.screenshot(path=os.path.join(CAPT, "pc-balance.png"), full_page=True)

    # Presupuestos: proponer, editar y deshacer
    p.click(".nav-btn[data-view=presupuestos]")
    p.click("#topActions [data-act=bud-propose]")
    p.wait_for_selector("#propDlg[open]")
    ok(p.locator("#propBody input[data-prop]").count() == 3, "propone las tres categorías de gasto")
    p.select_option("#propMethod", "med")
    ok("Ahorro previsto" in p.inner_text("#propCalc"), "calcula el ahorro previsto")
    p.click("#propForm button[type=submit]")
    p.wait_for_selector("text=3 presupuestos creados")
    ok(p.evaluate(f"() => {F}.budgets().map(b=>b.amountCents).sort((a,b)=>a-b)") == [10000, 30000, 75000], "presupuestos con la mediana redondeada a 5 €")
    p.click("[data-act=bud-edit] >> nth=0")
    p.wait_for_selector("#budDlg[open]")
    ok(p.locator("#budHelp .bud-opt").count() == 7, "el diálogo ofrece las medidas del histórico")
    p.fill("#budAmount", "50")
    p.click("#budForm button[type=submit]")
    p.wait_for_timeout(200)
    p.screenshot(path=os.path.join(CAPT, "pc-presupuestos.png"), full_page=True)
    p.click("body")
    p.keyboard.press("Control+z")
    p.wait_for_timeout(200)
    ok(p.evaluate(f"() => {F}.budgets().map(b=>b.amountCents).sort((a,b)=>a-b)") == [10000, 30000, 75000], "Ctrl+Z deshace el cambio de presupuesto")
    p.keyboard.press("Control+z")
    p.wait_for_timeout(200)
    ok(p.evaluate(f"() => {F}.budgets().length") == 0, "y la creación de los presupuestos")

    # Resumen
    p.keyboard.press("Alt+1")
    ok(p.locator(".vcard").count() >= 6 and p.locator(".hb").count() >= 3, "resumen con patrimonio, mes, año, gráfico, categorías y avisos")
    p.screenshot(path=os.path.join(CAPT, "pc-resumen.png"), full_page=True)
    p.keyboard.press("Alt+2")
    ok(p.evaluate("() => window.__fin.ui.view") == "estadisticas", "Alt+2 lleva a Estadísticas")
    for v in ["resumen", "estadisticas", "balance", "presupuestos"]:
        p.click(f".nav-btn[data-view={v}]")
        sin_desborde(p, "PC " + v)
    # Oscuro
    p.evaluate("() => { document.documentElement.dataset.theme='dark'; }")
    for v in ["resumen", "estadisticas", "balance"]:
        p.click(f".nav-btn[data-view={v}]")
        p.wait_for_timeout(150)
        p.screenshot(path=os.path.join(CAPT, f"pc-{v}-oscuro.png"), full_page=True)
    ok(not errores, "sin errores en la consola (estadísticas): " + "; ".join(errores[:3]))
    estado = p.evaluate("() => window.__fin.backupData()")
    ctx.close()
    return estado


with sync_playwright() as pw:
    b = pw.chromium.launch()
    flujo_importacion(b)
    est = flujo_pc(b)
    est2 = flujo_estadisticas(b)
    flujo_estrecho(b, est)
    flujo_estrecho(b, est2)
    b.close()

print()
print("RESULTADO:", "todo correcto" if not fallos else f"{len(fallos)} fallos")
sys.exit(1 if fallos else 0)
