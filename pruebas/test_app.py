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
    p.fill("#movLabels", "casa, semanal")
    p.click("#movForm button[type=submit]")
    p.wait_for_selector("text=Movimiento añadido")

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

    for v in ["resumen", "movimientos", "importar", "controles", "cuentas", "categorias", "reglas", "ajustes", "instrucciones"]:
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
    p.click("#accForm button[type=submit]")
    p.wait_for_selector("text=5 nuevos")
    p.click("[data-act=rv-confirm]")
    p.wait_for_selector("text=5 movimientos importados")
    estado = p.evaluate("""() => { const S = window.__fin.S, ms = [...S.movements.values()];
      const liq = ms.filter(m => m.kind === 'transferencia' && Math.abs(m.amountCents) === 5530);
      const cafes = ms.filter(m => m.rawConcept === 'Cafeteria plaza').length;
      return {pares: liq.length === 2 && liq[0].transferPairId && liq[0].transferPairId === liq[1].transferPairId, cafes}; }""")
    ok(estado["pares"], "la liquidación de la tarjeta queda emparejada (cuenta ↔ tarjeta)")
    ok(estado["cafes"] == 2, "dos cafés iguales el mismo día se mantienen los dos")
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
    # Volver a importar lo mismo no duplica nada
    n = p.evaluate("() => window.__fin.S.movements.size")
    p.evaluate("() => { window.__fin.imp.files = []; }")
    importar(p, "bbva-cuenta-septiembre.xlsx")
    ok("0 nuevos" in p.inner_text("#view") and "Este archivo ya se importó" in p.inner_text("#view"), "reimportar el mismo archivo: 0 nuevos")
    ok(p.evaluate("() => window.__fin.S.movements.size") == n, "no se ha añadido nada")
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
    p.click("[data-act=undo-import] >> nth=0")
    p.click("#cfmOk")
    p.wait_for_selector("text=Importación deshecha")
    vuelta = p.evaluate("""() => { const m = [...window.__fin.S.movements.values()].find(m => m.amountCents === -100000); return [m.kind, m.transferPairId]; }""")
    ok(vuelta == ["gasto", None], "al deshacer, la transferencia de BBVA vuelve a ser como antes")
    sin_desborde(p, "PC importar")
    ok(not errores, "sin errores en la consola (importación): " + "; ".join(errores[:3]))
    ctx.close()


def flujo_estrecho(browser, estado):
    errores = []
    ctx, p = nueva_pagina(browser, 361, 780, errores)
    print("Ventana estrecha")
    # Cargar los mismos datos para ver las vistas llenas
    p.evaluate("""(d) => window.__fin.commit('', cs => { for (const s of Object.keys(d.stores)) for (const r of d.stores[s]) cs.put(s, r); }, {noUndo:true})""", estado)
    for v in ["resumen", "movimientos", "importar", "controles", "cuentas", "categorias", "reglas", "ajustes", "instrucciones"]:
        p.click("#menuBtn")
        p.click(f".nav-btn[data-view={v}]")
        p.wait_for_timeout(250)
        sin_desborde(p, "Estrecha " + v)
        if v in ("resumen", "movimientos", "controles"):
            p.screenshot(path=os.path.join(CAPT, f"movil-{v}.png"), full_page=True)
    p.keyboard.press("n")
    p.wait_for_selector("#movDlg[open]")
    caja = p.evaluate("() => { const r = document.querySelector('#movDlg').getBoundingClientRect(); return [r.left, r.right, innerWidth]; }")
    ok(caja[0] >= 0 and caja[1] <= caja[2], "el diálogo cabe en la pantalla")
    p.screenshot(path=os.path.join(CAPT, "movil-dialogo.png"))
    ok(not errores, "sin errores en la consola (estrecha): " + "; ".join(errores[:3]))
    ctx.close()


with sync_playwright() as pw:
    b = pw.chromium.launch()
    flujo_importacion(b)
    est = flujo_pc(b)
    flujo_estrecho(b, est)
    b.close()

print()
print("RESULTADO:", "todo correcto" if not fallos else f"{len(fallos)} fallos")
sys.exit(1 if fallos else 0)
