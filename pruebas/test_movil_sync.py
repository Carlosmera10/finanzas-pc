"""Pruebas del móvil (Android) y de la sincronización entre dispositivos, con Playwright + Chromium sin interfaz.

GitHub se simula: las llamadas a api.github.com las contesta un Gist falso en memoria,
así que no sale nada a internet y no hace falta ningún token real.

Uso (desde la raíz del repositorio):
  python3 -m http.server 8000 &          # servir el repositorio
  python3 pruebas/test_movil_sync.py
  pkill -f "http.serve[r] 8000"          # pararlo
"""
import json
import os
import sys
import time

from playwright.sync_api import sync_playwright

URL = "http://localhost:8000/"
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAPT = os.path.join(RAIZ, "pruebas", "capturas")
SINT = os.path.join(RAIZ, "pruebas", "sinteticos")
os.makedirs(CAPT, exist_ok=True)
F = "window.__fin"
TOKEN = "github_pat_prueba_inventado"
CLAVE = "contraseña de prueba"

fallos = []


def ok(cond, msg):
    print(("  ✔ " if cond else "  ✖ ") + msg)
    if not cond:
        fallos.append(msg)


# ---------------- Gist falso ----------------
class GistFalso:
    def __init__(self):
        self.gists = {}
        self.peticiones = []
        self.limite_truncado = 30_000  # por encima, se da por «raw_url», como GitHub con más de 1 MB

    def manejar(self, route):
        req = route.request
        url = req.url
        cors = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "Authorization, Content-Type, Accept",
                "Access-Control-Allow-Methods": "GET, POST, PATCH, OPTIONS", "Content-Type": "application/json"}
        if req.method == "OPTIONS":
            return route.fulfill(status=204, headers=cors, body="")
        self.peticiones.append((req.method, url))
        if url.startswith("https://gist.raw.test/"):
            gid = url.rsplit("/", 1)[1]
            return route.fulfill(status=200, headers={**cors, "Content-Type": "text/plain"}, body=self.gists[gid]["content"])
        if req.headers.get("authorization") != "Bearer " + TOKEN:
            return route.fulfill(status=401, headers=cors, body=json.dumps({"message": "Bad credentials"}))
        path = url.split("api.github.com", 1)[1]
        if req.method == "GET" and path.startswith("/gists?"):
            lista = [{"id": g, "created_at": v["created_at"], "files": {v["name"]: {}}} for g, v in self.gists.items()]
            return route.fulfill(status=200, headers=cors, body=json.dumps(lista))
        if req.method == "POST" and path == "/gists":
            body = json.loads(req.post_data)
            ok(body.get("public") is False, "el Gist se crea secreto")
            name, f = next(iter(body["files"].items()))
            gid = "g%d" % (len(self.gists) + 1)
            self.gists[gid] = {"name": name, "content": f["content"], "created_at": "2026-10-31T10:00:00Z"}
            return route.fulfill(status=201, headers=cors, body=json.dumps({"id": gid}))
        gid = path.split("/gists/", 1)[1]
        if gid not in self.gists:
            return route.fulfill(status=404, headers=cors, body="{}")
        g = self.gists[gid]
        if req.method == "PATCH":
            body = json.loads(req.post_data)
            g["content"] = body["files"][g["name"]]["content"]
            return route.fulfill(status=200, headers=cors, body="{}")
        trunc = len(g["content"]) > self.limite_truncado
        f = {"truncated": trunc, "raw_url": "https://gist.raw.test/" + gid, "content": g["content"][:1000] if trunc else g["content"]}
        return route.fulfill(status=200, headers=cors, body=json.dumps({"id": gid, "files": {g["name"]: f}}))


def nueva_pagina(browser, gist, errores, movil=False):
    if movil:  # Chrome de Android (tamaño de un móvil normal, táctil)
        ctx = browser.new_context(viewport={"width": 412, "height": 915}, device_scale_factor=2.6, is_mobile=True, has_touch=True,
                                  locale="es-ES", timezone_id="Europe/Madrid", accept_downloads=True,
                                  user_agent="Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Mobile Safari/537.36")
    else:
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="es-ES", timezone_id="Europe/Madrid", accept_downloads=True)
    ctx.route("**/fonts.googleapis.com/**", lambda r: r.abort())
    ctx.route("**/fonts.gstatic.com/**", lambda r: r.abort())
    ctx.route("https://api.github.com/**", gist.manejar)
    ctx.route("https://gist.raw.test/**", gist.manejar)
    p = ctx.new_page()
    p.on("console", lambda m: errores.append(m.text) if m.type == "error" and "fonts.g" not in (m.location or {}).get("url", "") else None)
    p.on("pageerror", lambda e: errores.append(str(e)))
    p.goto(URL)
    p.wait_for_function("window.__fin && window.__fin.ready()")
    return ctx, p


def sin_desborde(p, nombre):
    w = p.evaluate("() => [document.documentElement.scrollWidth, window.innerWidth]")
    ok(w[0] <= w[1], f"{nombre}: sin desborde horizontal ({w[0]} ≤ {w[1]})")


# Datos inventados: 2 cuentas, categorías y unos 4.000 movimientos de 3 años
SEMILLA_JS = r"""
() => {
  const F = window.__fin, acc = [
    {id: 'A', name: 'Cuenta A', bank: 'bbva', kind: 'corriente', openingCents: 100000, openingDate: '2023-01-01', order: 1},
    {id: 'T', name: 'Tarjeta A', bank: 'bbva', kind: 'tarjeta_credito', linkedAccountId: 'A', openingCents: 0, openingDate: '2023-01-01', order: 2},
  ].map(F.normAccount);
  const cat = [{id: 'c1', name: 'Comida'}, {id: 'c2', name: 'Super', parent: 'c1'}, {id: 'i1', name: 'Ingresos', kind: 'ingreso'}].map(F.normCategory);
  const movs = [];
  let n = 0;
  for (let d = 0; d < 1100; d++) {
    const dt = F.addDays('2023-01-01', d);
    for (let k = 0; k < 3; k++) movs.push(F.normMovement({id: 'm' + (++n), accountId: k ? 'T' : 'A', date: dt, amountCents: -(100 + (n * 37) % 9000),
      kind: 'gasto', categoryId: 'c2', payee: 'Comercio ' + (n % 40), rawConcept: 'COMPRA TARJ. 1234 COMERCIO ' + (n % 40) + ' MADRID ES',
      concept: 'Comercio ' + (n % 40), source: 'import', reviewed: true, labels: n % 7 ? [] : ['Viaje 🌴']}));
    if (d % 30 === 0) movs.push(F.normMovement({id: 'm' + (++n), accountId: 'A', date: dt, amountCents: 250000, kind: 'ingreso', categoryId: 'i1', payee: 'Empresa', source: 'import'}));
  }
  return F.commit('', cs => { for (const a of acc) cs.put('accounts', a); for (const c of cat) cs.put('categories', c); for (const m of movs) cs.put('movements', m);
    cs.put('meta', {key: 'budgets', value: [{id: 'b1', categoryId: 'c1', amountCents: 40000}]}); }, {noUndo: true}).then(() => movs.length);
}
"""

MERGE_JS = r"""
() => {
  const F = window.__fin, out = [], eq = (a, b, msg) => out.push([JSON.stringify(a) === JSON.stringify(b), msg + ' → ' + JSON.stringify(a)]);
  const mv = (id, at, extra = {}) => F.normMovement({id, accountId: 'A', date: '2026-10-01', amountCents: -100, kind: 'gasto', createdAt: '2026-10-01T00:00:00Z', updatedAt: at, ...extra});
  const st = (movs, del = {}) => ({stores: {movements: new Map(movs.map(m => [m.id, m]))}, del});
  const T = h => '2026-10-31T' + String(h).padStart(2, '0') + ':00:00.000Z';
  // Gana el cambio más reciente
  let L = st([mv('a', T(1), {payee: 'viejo'})]), R = st([mv('a', T(2), {payee: 'nuevo'})]);
  let m = F.syncMerge(L, R);
  eq([m.stores.movements.get('a').payee, m.local.length, m.toRemote], ['nuevo', 1, false], 'gana el más reciente (del otro dispositivo)');
  m = F.syncMerge(R, L);
  eq([m.stores.movements.get('a').payee, m.local.length, m.toRemote], ['nuevo', 0, true], 'gana el más reciente (de este dispositivo)');
  // Borrado propagado
  L = st([], {'movements|b': T(3)}); R = st([mv('b', T(2))]);
  m = F.syncMerge(L, R);
  eq([m.stores.movements.has('b'), m.toRemote, m.del['movements|b']], [false, true, T(3)], 'un borrado posterior al último cambio se respeta');
  m = F.syncMerge(R, L);
  eq([m.stores.movements.has('b'), m.local.map(e => [e.key, e.value === undefined]).filter(x => x[0] === 'b')], [false, [['b', true]]], 'y llega al otro dispositivo como borrado');
  // Cambio posterior al borrado: revive
  L = st([mv('c', T(6))]); R = st([], {'movements|c': T(5)});
  m = F.syncMerge(L, R);
  eq([m.stores.movements.has('c'), 'movements|c' in m.del, m.toRemote], [true, false, true], 'un cambio posterior al borrado lo mantiene');
  // Empate de hora con distinto contenido: los dos dispositivos eligen lo mismo
  const x1 = mv('d', T(4), {payee: 'X'}), x2 = mv('d', T(4), {payee: 'Y'});
  const a = F.syncMerge(st([x1]), st([x2])).stores.movements.get('d').payee, b = F.syncMerge(st([x2]), st([x1])).stores.movements.get('d').payee;
  eq(a === b, true, 'empate: los dos dispositivos eligen la misma versión');
  // Iguales: nada que hacer
  m = F.syncMerge(st([mv('e', T(1))]), st([mv('e', T(1))]));
  eq([m.local.length, m.toRemote], [0, false], 'iguales: no hay cambios ni subida');
  // Orden de los campos distinto: no cuenta como cambio
  eq(F.canonStr({b: 1, a: {d: 2, c: [3, {f: 1, e: 2}]}}) === F.canonStr({a: {c: [3, {e: 2, f: 1}], d: 2}, b: 1}), true, 'el orden de los campos no importa');
  // Borrados muy antiguos se olvidan
  m = F.syncMerge(st([], {'movements|z': '2020-01-01T00:00:00Z'}), st([]));
  eq('movements|z' in m.del, false, 'los borrados de hace más de 400 días se olvidan');
  return out;
}
"""


def activar(p, nueva_clave=True, clave=CLAVE):
    if p.locator("#bnMore").is_visible():
        p.click("#bnMore")
    p.click(".nav-btn[data-view=ajustes]")
    p.fill("#syncToken", TOKEN)
    if nueva_clave:
        p.fill("#syncPass", clave)
        p.fill("#syncPass2", clave)
    p.click("[data-act=sync-on]")
    p.wait_for_function("() => { const s = window.__fin.syncState(); return !s.busy && s.status !== 'syncing'; }", timeout=60000)
    p.wait_for_timeout(300)


def sincronizar(p):
    r = p.evaluate(f"() => {F}.syncNow({{force:true}}).then(r => r.ok)")
    return r


def flujo(browser):
    gist = GistFalso()
    err_pc, err_mv = [], []
    print("Fusión (unitarias)")
    ctx_pc, pc = nueva_pagina(browser, gist, err_pc)
    for good, msg in pc.evaluate(MERGE_JS):
        ok(good, msg)

    print("Sincronización PC → móvil")
    n = pc.evaluate(SEMILLA_JS)
    activar(pc)
    st = pc.evaluate(f"() => {F}.syncState()")
    ok(st["status"] == "ok" and st["cfg"]["gistId"] == "g1", f"el PC activa la sincronización y crea el Gist → {st['status']} {st['err']}")
    tam = len(gist.gists["g1"]["content"])
    ok(tam < 900_000, f"tamaño de la copia cifrada con {n} movimientos: {tam // 1024} KB (cabe bien en un Gist)")
    ok("Comercio" not in gist.gists["g1"]["content"] and "Cuenta A" not in gist.gists["g1"]["content"], "en GitHub no se ve nada en claro")
    ok(pc.locator("#syncStatus").inner_text().startswith("Activa."), "Ajustes muestra «Activa.»")

    ctx_mv, mv = nueva_pagina(browser, gist, err_mv, movil=True)
    print("Móvil (Android)")
    ok(mv.locator("#bottomNav").is_visible() and mv.evaluate("() => document.querySelector('#sidebar').getBoundingClientRect().right <= 0"), "barra inferior visible y menú lateral oculto")
    ok(mv.locator(".empty [data-view=ajustes]").count() == 1, "sin datos, el Resumen ofrece traerlos del otro dispositivo")
    activar(mv)
    cuenta = mv.evaluate(f"() => {F}.S.movements.size")
    ok(cuenta == n, f"el móvil recibe todos los movimientos ({cuenta} de {n})")
    ok(mv.evaluate(f"() => {F}.S.accounts.size") == 2 and mv.evaluate(f"() => (window.__fin.budgets()||[]).length") == 1, "y las cuentas y los presupuestos")
    ok(any(u.startswith("https://gist.raw.test/") for _, u in gist.peticiones), "lee la copia grande por su dirección completa (más de 1 MB en GitHub)")

    # Vistas del móvil sin desbordes
    for v in ["resumen", "movimientos", "estadisticas"]:
        mv.click(f"[data-bn={v}]")
        mv.wait_for_timeout(250)
        sin_desborde(mv, "Móvil " + v)
        ok(mv.get_attribute(f"[data-bn={v}]", "aria-current") == "page", f"la barra marca {v}")
        mv.screenshot(path=os.path.join(CAPT, f"android-{v}.png"))
    for v in ["presupuestos", "balance", "importar", "controles", "cuentas", "categorias", "reglas", "ajustes", "instrucciones"]:
        mv.click("#bnMore")
        mv.click(f".nav-btn[data-view={v}]")
        mv.wait_for_timeout(200)
        ok(not mv.evaluate("() => document.body.classList.contains('drawer-open')"), f"el menú se cierra al ir a {v}")
        sin_desborde(mv, "Móvil " + v)
    ok(mv.locator(".folder-line").is_hidden(), "en el móvil no se ofrece la carpeta de importación")

    # Movimientos en tarjetas y filtros plegables
    mv.click("[data-bn=movimientos]")
    alto = mv.evaluate("() => document.querySelector('tr[data-mov]').getBoundingClientRect().height")
    ok(40 <= alto <= 110, f"cada movimiento es una tarjeta compacta ({alto:.0f} px de alto)")
    ok(not mv.locator(".mv-tbl thead").is_visible(), "sin cabecera de tabla en el móvil")
    ok(not mv.locator(".f-acc").is_visible() and mv.locator("#movSearch").is_visible(), "filtros plegados con la búsqueda a la vista")
    mv.click("[data-act=toggle-filters]")
    ok(mv.locator(".f-acc").is_visible(), "«Filtros» los despliega")
    mv.select_option(".f-acc", "T")
    mv.click("[data-act=toggle-filters]")
    ok("1" in mv.inner_text("[data-act=toggle-filters]"), "al plegarlos, el botón dice cuántos hay puestos")
    mv.click("[data-act=toggle-filters]")
    mv.click("[data-act=clear-filters]")
    mv.screenshot(path=os.path.join(CAPT, "android-movimientos-tarjetas.png"))

    # Apuntar un gasto con el botón +
    mv.click("#bnNew")
    mv.wait_for_selector("#movDlg[open]")
    caja = mv.evaluate("() => { const r = document.querySelector('#movDlg').getBoundingClientRect(); return [r.left, r.right, r.bottom, innerWidth, innerHeight]; }")
    ok(caja[0] >= 0 and caja[1] <= caja[3] and caja[2] <= caja[4] + 1, "el diálogo ocupa la pantalla como una hoja desde abajo")
    ok(mv.get_attribute("#movAmount", "inputmode") == "decimal", "el importe abre el teclado numérico")
    mv.screenshot(path=os.path.join(CAPT, "android-nuevo-movimiento.png"))
    mv.fill("#movPayee", "Panadería del móvil")
    mv.fill("#movAmount", "3,40")
    mv.select_option("#movAcc", "A")
    mv.click("#movSave")
    mv.wait_for_timeout(300)
    nuevo = mv.evaluate(f"() => [...{F}.S.movements.values()].find(m => m.payee === 'Panadería del móvil')")
    ok(bool(nuevo) and nuevo["amountCents"] == -340, "se apunta el gasto en el móvil")
    ok(mv.evaluate(f"() => {F}.syncState().dirty"), "queda pendiente de enviar")
    mv.wait_for_function(f"() => !{F}.syncState().dirty && !{F}.syncState().busy", timeout=30000)
    ok(True, "se envía solo unos segundos después")

    print("Sincronización móvil → PC")
    ok(sincronizar(pc), "el PC sincroniza")
    ok(pc.evaluate(f"() => [...{F}.S.movements.values()].some(m => m.payee === 'Panadería del móvil')"), "el PC recibe el gasto apuntado en el móvil")

    # Borrado en el PC → desaparece en el móvil; y deshacer lo recupera
    pc.evaluate(f"() => {F}.commit('Borrado', cs => cs.del('movements', 'm5'))")
    ok(sincronizar(pc), "el PC envía el borrado")
    ok(sincronizar(mv) and not mv.evaluate(f"() => {F}.S.movements.has('m5')"), "el borrado llega al móvil")
    pc.evaluate(f"() => {F}.undo()")
    pc.wait_for_timeout(200)
    ok(sincronizar(pc) and sincronizar(mv) and mv.evaluate(f"() => {F}.S.movements.has('m5')"), "«Deshacer» en el PC lo recupera también en el móvil")

    # Cambios en los dos a la vez: en cada movimiento gana el último
    pc.evaluate(f"() => {F}.commit('', cs => cs.put('movements', {{...{F}.S.movements.get('m10'), payee: 'Cambio del PC'}}))")
    time.sleep(0.05)
    mv.evaluate(f"() => {F}.commit('', cs => cs.put('movements', {{...{F}.S.movements.get('m10'), payee: 'Cambio del móvil'}}))")
    mv.evaluate(f"() => {F}.commit('', cs => cs.put('movements', {{...{F}.S.movements.get('m11'), notes: 'Nota del móvil'}}))")
    pc.evaluate(f"() => {F}.commit('', cs => cs.put('movements', {{...{F}.S.movements.get('m12'), notes: 'Nota del PC'}}))")
    for d in (pc, mv, pc):
        sincronizar(d)
    r_pc = pc.evaluate(f"() => ['m10','m11','m12'].map(id => {{ const m = {F}.S.movements.get(id); return [m.payee, m.notes]; }})")
    r_mv = mv.evaluate(f"() => ['m10','m11','m12'].map(id => {{ const m = {F}.S.movements.get(id); return [m.payee, m.notes]; }})")
    ok(r_pc == r_mv and r_pc[0][0] == "Cambio del móvil" and r_pc[1][1] == "Nota del móvil" and r_pc[2][1] == "Nota del PC",
       f"cambios cruzados: se conservan los dos y en el mismo movimiento gana el último → {r_pc}")
    ok(pc.evaluate(f"() => {F}.S.movements.size") == mv.evaluate(f"() => {F}.S.movements.size"), "los dos dispositivos acaban con los mismos movimientos")

    # Ajustes propios de cada dispositivo
    pc.evaluate(f"() => {F}.commit('', cs => cs.put('meta', {{key:'lastBackup', value:'2026-10-31T10:00:00.000Z'}}), {{noUndo:true}})")
    sincronizar(pc); sincronizar(mv)
    ok(mv.evaluate(f"() => {F}.S.meta.get('lastBackup')") is None, "la fecha de la última copia no se sincroniza")

    print("Bluecoins opcional")
    mv.click("#bnMore"); mv.click(".nav-btn[data-view=ajustes]")
    mv.click("#bcSeg [data-bc='0']")
    mv.wait_for_timeout(150)
    ok(mv.evaluate("() => document.body.classList.contains('no-bc')"), "«No lo uso» oculta lo de Bluecoins")
    mv.click("#bnMore"); mv.click(".nav-btn[data-view=cuentas]")
    ok(not mv.locator("th.bc-only").first.is_visible(), "las cuentas no muestran la columna «En Bluecoins»")
    mv.click("[data-bn=movimientos]")
    ok(mv.locator(".f-state option[value=noexp]").count() == 0, "el filtro «Sin exportar a Bluecoins» desaparece")
    sincronizar(mv); sincronizar(pc)
    ok(pc.evaluate("() => document.body.classList.contains('no-bc')"), "la elección llega también al PC")
    pc.click(".nav-btn[data-view=ajustes]")
    pc.click("#bcSeg [data-bc='1']")
    pc.wait_for_timeout(200)
    ok(not pc.evaluate("() => document.body.classList.contains('no-bc')"), "«Lo uso» lo vuelve a mostrar")

    print("Errores")
    # Contraseña distinta en un tercer dispositivo
    err3 = []
    ctx3, p3 = nueva_pagina(browser, gist, err3)
    activar(p3, clave="otra contraseña")
    ok(p3.locator("#cfmDlg[open]").count() == 1, "con otra contraseña ofrece sustituir la copia de GitHub")
    p3.click("#cfmDlg [data-close] >> nth=0") if p3.locator("#cfmDlg [data-close]").count() else p3.keyboard.press("Escape")
    p3.wait_for_timeout(300)
    ok(p3.evaluate(f"() => {F}.syncState().cfg") is None and p3.evaluate(f"() => {F}.S.movements.size") == 0, "si no se acepta, no se activa ni se toca nada")
    ctx3.close()
    # Token caducado → en pausa, punto rojo en «Más»
    mv.evaluate("() => { const c = JSON.parse(localStorage.getItem('fin_sync')); c.token = 'caducado'; localStorage.setItem('fin_sync', JSON.stringify(c)); }")
    mv.reload()
    mv.wait_for_function("window.__fin && window.__fin.ready()")
    mv.wait_for_function(f"() => {F}.syncState().status === 'error'", timeout=30000)
    ok(mv.evaluate(f"() => {F}.syncState().halt") == "token", "token no válido: sincronización en pausa")
    ok(mv.locator(".bn-dot").is_visible(), "punto rojo en «Más»")
    mv.click("#bnMore")
    ok(mv.locator("#syncNote").is_visible(), "aviso «Sincronización en pausa» en el menú")
    mv.click("#syncNote")
    ok("no es válido" in mv.inner_text("#syncStatus"), "Ajustes explica el motivo")
    mv.screenshot(path=os.path.join(CAPT, "android-ajustes-sincronizacion.png"), full_page=True)
    activar(mv, nueva_clave=False)
    ok(mv.evaluate(f"() => {F}.syncState().status") == "ok", "al volver a pegar el token, se reanuda")

    ok(not err_pc, "sin errores en la consola (PC): " + "; ".join(err_pc[:3]))
    ok(not [e for e in err_mv if "401" not in e], "sin errores en la consola (móvil): " + "; ".join(err_mv[:3]))
    ctx_pc.close()
    ctx_mv.close()


def flujo_importar_movil(browser):
    """Importar los archivos del banco en el móvil, con la configuración que llega del PC."""
    gist = GistFalso()
    err_pc, err_mv = [], []
    print("Importar en el móvil")
    ctx_pc, pc = nueva_pagina(browser, gist, err_pc)
    pc.click(".nav-btn[data-view=importar]")
    # En el PC: cuentas creadas al importar septiembre de BBVA, ING y Trade Republic
    for nombre in ["bbva-cuenta-septiembre.xlsx", "ing-cuenta.xls"]:
        pc.set_input_files("#fileInput", os.path.join(SINT, nombre))
        pc.wait_for_selector(f".file-item[aria-current=true] >> text={nombre}")
        pc.click("[data-act=rv-new-acc]")
        pc.click("#accForm button[type=submit]")
        pc.wait_for_function("document.querySelector('#rvAcc') && document.querySelector('#rvAcc').value !== ''")
        pc.click("[data-act=rv-confirm]")
        pc.wait_for_selector("text=movimientos importados")
        pc.wait_for_timeout(300)
    n_pc = pc.evaluate(f"() => {F}.S.movements.size")
    activar(pc)

    ctx_mv, mv = nueva_pagina(browser, gist, err_mv, movil=True)
    activar(mv)
    ok(mv.evaluate(f"() => {F}.S.accounts.size") == 2, "el móvil recibe las cuentas del PC con sus identificadores")
    mv.click("#bnMore")
    mv.click(".nav-btn[data-view=importar]")
    ok(mv.locator("[data-act=pick-files]").is_visible(), "botón «Elegir archivos» a la vista")
    # BBVA octubre (se solapa con septiembre) desde el móvil
    mv.set_input_files("#fileInput", os.path.join(SINT, "bbva-cuenta-octubre.xlsx"))
    mv.wait_for_selector(".file-item[aria-current=true] >> text=bbva-cuenta-octubre.xlsx")
    ok(mv.eval_on_selector("#rvAcc", "s => s.options[s.selectedIndex].text").startswith("BBVA"), "reconoce sola la cuenta BBVA")
    txt = mv.inner_text("#view")
    ok("2 nuevos" in txt and "3 ya estaban" in txt, "no duplica lo que ya importó el PC (2 nuevos, 3 ya estaban)")
    mv.wait_for_timeout(400)
    ok(mv.evaluate("() => document.querySelector('#sidebar').getBoundingClientRect().right") <= 0, "el menú lateral queda oculto del todo")
    ok(mv.locator(".folder-line").is_hidden(), "sin carpeta de importación en el móvil")
    sin_desborde(mv, "Móvil revisión de la importación")
    mv.screenshot(path=os.path.join(CAPT, "android-importar-revision.png"), full_page=True)
    mv.click("[data-act=rv-confirm]")
    mv.wait_for_selector("text=2 movimientos importados en BBVA · el saldo cuadra")
    ok(True, "BBVA importado en el móvil y el saldo cuadra")
    # ING (.xls binario de Excel 97-2003) en el móvil: ya importado en el PC → nada nuevo
    mv.set_input_files("#fileInput", os.path.join(SINT, "ing-cuenta.xls"))
    mv.wait_for_selector(".file-item[aria-current=true] >> text=ing-cuenta.xls")
    ok("ya se importó" in mv.inner_text("#view").lower() or "0 nuevos" in mv.inner_text("#view"), "el archivo de ING ya importado en el PC se reconoce")
    # Trade Republic (CSV): cuenta nueva desde el móvil
    mv.set_input_files("#fileInput", os.path.join(SINT, "trade-republic.csv"))
    mv.wait_for_selector(".file-item[aria-current=true] >> text=trade-republic.csv")
    mv.click("[data-act=rv-new-acc]")
    mv.click("#accForm button[type=submit]")
    mv.wait_for_function("document.querySelector('#rvAcc') && document.querySelector('#rvAcc').value !== ''")
    mv.click("[data-act=rv-confirm]")
    mv.wait_for_selector("text=movimientos importados en Trade Republic")
    ok(True, "Trade Republic importado en el móvil con cuenta nueva")
    mv.wait_for_function(f"() => !{F}.syncState().dirty && !{F}.syncState().busy", timeout=30000)
    ok(sincronizar(pc), "el PC sincroniza")
    r = pc.evaluate(f"() => [{F}.S.movements.size, {F}.S.accounts.size, {F}.S.imports.size]")
    rm = mv.evaluate(f"() => [{F}.S.movements.size, {F}.S.accounts.size, {F}.S.imports.size]")
    ok(r == rm and r[0] > n_pc and r[1] == 3, f"lo importado en el móvil llega al PC (movimientos, cuentas, importaciones) → PC {r} · móvil {rm}")
    # El mismo archivo en el PC ya no se vuelve a importar
    pc.click(".nav-btn[data-view=importar]")
    pc.set_input_files("#fileInput", os.path.join(SINT, "bbva-cuenta-octubre.xlsx"))
    pc.wait_for_selector(".file-item[aria-current=true] >> text=bbva-cuenta-octubre.xlsx")
    ok(pc.locator("[data-act=rv-confirm]").count() == 0 or pc.is_disabled("[data-act=rv-confirm]") or "0 nuevos" in pc.inner_text("#view"),
       "en el PC ese archivo ya figura como importado")
    ok(not err_pc and not err_mv, "sin errores en la consola: " + "; ".join((err_pc + err_mv)[:3]))
    ctx_pc.close()
    ctx_mv.close()


with sync_playwright() as pw:
    b = pw.chromium.launch()
    flujo(b)
    flujo_importar_movil(b)
    b.close()

print()
print("RESULTADO:", "todo correcto" if not fallos else f"{len(fallos)} fallos")
sys.exit(1 if fallos else 0)
