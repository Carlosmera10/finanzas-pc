"""Genera archivos de prueba SINTÉTICOS (datos inventados) en pruebas/sinteticos/.

Cubren los formatos que suelen descargar los bancos españoles:
  - .xlsx de verdad, con filas de título, fechas como fecha de Excel e importes como número;
  - .xls que en realidad es HTML con una tabla;
  - .xls que en realidad es XML de Excel 2003;
  - .csv con punto y coma, coma decimal y codificación Windows-1252.
Cuando lleguen los archivos reales de cada banco, se añadirán aquí sus copias sintéticas
con la misma estructura (nunca los datos reales).

Uso: python3 pruebas/generar_sinteticos.py
"""
import datetime as dt
import os

from openpyxl import Workbook

DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sinteticos")
os.makedirs(DIR, exist_ok=True)

FILAS = [
    # fecha, fecha valor, concepto, importe, saldo
    (dt.date(2026, 9, 1), dt.date(2026, 9, 1), "TRANSFERENCIA RECIBIDA NOMINA EMPRESA FICTICIA", 2150.00, 3150.00),
    (dt.date(2026, 9, 2), dt.date(2026, 9, 2), "PAGO CON TARJETA SUPERMERCADO EJEMPLO", -45.67, 3104.33),
    (dt.date(2026, 9, 2), dt.date(2026, 9, 2), "PAGO CON TARJETA CAFETERÍA PLAZA", -1.80, 3102.53),
    (dt.date(2026, 9, 2), dt.date(2026, 9, 2), "PAGO CON TARJETA CAFETERÍA PLAZA", -1.80, 3100.73),
    (dt.date(2026, 9, 5), dt.date(2026, 9, 5), "RECIBO LUZ COMPAÑÍA INVENTADA", -62.15, 3038.58),
    (dt.date(2026, 9, 10), dt.date(2026, 9, 10), "BIZUM ENVIADO CENA", -20.00, 3018.58),
    (dt.date(2026, 9, 15), dt.date(2026, 9, 15), "TRASPASO A CUENTA AHORRO", -500.00, 2518.58),
    (dt.date(2026, 9, 20), dt.date(2026, 9, 21), "RETIRADA CAJERO", -1234.56, 1284.02),
]


def xlsx():
    wb = Workbook()
    ws = wb.active
    ws.title = "Movimientos"
    ws["A1"] = "Últimos movimientos"
    ws["A2"] = "Cuenta: ES00 0000 0000 0000 0000 0000"
    ws.append([])
    ws.append(["F. Operación", "F. Valor", "Concepto", "Importe", "Saldo"])
    for f, fv, c, imp, saldo in FILAS:
        ws.append([f, fv, c, imp, saldo])
        ws.cell(ws.max_row, 1).number_format = "dd/mm/yyyy"
        ws.cell(ws.max_row, 2).number_format = "dd/mm/yyyy"
        ws.cell(ws.max_row, 4).number_format = '#,##0.00\\ "€"'
    wb.save(os.path.join(DIR, "sintetico-xlsx.xlsx"))


def html_xls():
    filas = "".join(
        f"<tr><td>{f:%d/%m/%Y}</td><td>{c}</td><td>{str(f'{imp:,.2f}').replace(',', 'X').replace('.', ',').replace('X', '.')}</td></tr>"
        for f, _, c, imp, _ in FILAS
    )
    html = (
        '<html><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8"></head><body>'
        "<table><tr><td colspan=3>Movimientos de la cuenta</td></tr>"
        "<tr><th>Fecha</th><th>Concepto</th><th>Importe</th></tr>" + filas + "</table></body></html>"
    )
    with open(os.path.join(DIR, "sintetico-html.xls"), "w", encoding="utf-8") as fh:
        fh.write(html)


def xml2003():
    filas = "".join(
        f'<Row><Cell><Data ss:Type="DateTime">{f:%Y-%m-%d}T00:00:00.000</Data></Cell>'
        f'<Cell><Data ss:Type="String">{c}</Data></Cell><Cell><Data ss:Type="Number">{imp}</Data></Cell></Row>'
        for f, _, c, imp, _ in FILAS
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n<?mso-application progid="Excel.Sheet"?>\n'
        '<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">'
        '<Worksheet ss:Name="Movimientos"><Table>'
        '<Row><Cell><Data ss:Type="String">Fecha</Data></Cell><Cell><Data ss:Type="String">Concepto</Data></Cell><Cell><Data ss:Type="String">Importe</Data></Cell></Row>'
        + filas + "</Table></Worksheet></Workbook>"
    )
    with open(os.path.join(DIR, "sintetico-xml2003.xls"), "w", encoding="utf-8") as fh:
        fh.write(xml)


def csv_1252():
    lineas = ["Fecha;Concepto;Importe;Saldo"]
    for f, _, c, imp, saldo in FILAS:
        lineas.append(f'{f:%d/%m/%Y};"{c}";{imp:.2f};{saldo:.2f}'.replace(".", ","))
    with open(os.path.join(DIR, "sintetico-1252.csv"), "w", encoding="cp1252", newline="") as fh:
        fh.write("\r\n".join(lineas) + "\r\n")


if __name__ == "__main__":
    xlsx()
    html_xls()
    xml2003()
    csv_1252()
    print("Archivos generados en", DIR)


# ---------------------------------------------------------------------------
# Copias SINTÉTICAS con la misma estructura que los archivos reales de cada banco
# (datos inventados; los números de cuenta y tarjeta son ceros).
# ---------------------------------------------------------------------------
TARJETA = "0000000000001111"


def bbva_cuenta(nombre, filas, saldo_final):
    """filas en orden descendente (más reciente primero): (fecha valor, fecha, concepto, movimiento, importe)."""
    wb = Workbook(); ws = wb.active; ws.title = "Informe BBVA"
    ws["D2"] = "Últimos movimientos"
    ws["D3"] = "Fecha de generación del informe: 29/10/2026"
    ws.append([])
    for col, txt in zip("BCDEFGHIJ", ["F.Valor", "Fecha", "Concepto", "Movimiento", "Importe", "Divisa", "Disponible", "Divisa", "Observaciones"]):
        ws[f"{col}5"] = txt
    saldo = saldo_final
    for i, (fv, f, c, m, imp) in enumerate(filas):
        r = 6 + i
        for col, v in zip("BCDEFGHIJ", [fv, f, c, m, imp, "EUR", round(saldo, 2), "EUR", m.upper()]):
            ws[f"{col}{r}"] = v
        saldo = round(saldo - imp, 2)
    wb.save(os.path.join(DIR, nombre))


SEP = [  # más reciente primero
    ("30/09/2026", "30/09/2026", "Adeudo colegio ficticio", "Adeudo nº 0000000000000002", -100.00),
    ("30/09/2026", "30/09/2026", "Adeudo colegio ficticio", "Adeudo nº 0000000000000001", -100.00),
    ("28/09/2026", "28/09/2026", "Abono de nómina", "Empresa ficticia", 2000.00),
    ("27/09/2026", "28/09/2026", "Bizum", "Enviado: cena amigos", -20.00),
    ("15/09/2026", "15/09/2026", "Ret. efectivo  a debito con tarj.  ", "Otros", -40.00),
    ("05/09/2026", "04/09/2026", "Adeudo mensual de tarjeta", TARJETA, -55.30),
    ("01/09/2026", "01/09/2026", "Transferencia realizada", "Transferencia mensual ing", -1000.00),
]
OCT = [
    ("05/10/2026", "05/10/2026", "Adeudo de telefonica", "Adeudo nº 0000000000000003", -30.00),
    ("02/10/2026", "02/10/2026", "Bizum", "Recibido: devolucion", 15.00),
] + SEP[:3]  # se solapa con los tres últimos de septiembre
bbva_cuenta("bbva-cuenta-septiembre.xlsx", SEP, 5000.00)
bbva_cuenta("bbva-cuenta-octubre.xlsx", OCT, 5000.00 - 30.00 + 15.00)


def bbva_tarjeta():
    wb = Workbook(); ws = wb.active; ws.title = "Informe BBVA"
    ws["D2"] = "Listado de movimientos"
    ws["D3"] = "Fecha de generación del informe: 29/10/2026"
    for col, txt in zip("BCDEF", ["Fecha", "Tarjeta", "Concepto", "Importe", "Divisa"]):
        ws[f"{col}5"] = txt
    filas = [
        ("26/09/2026", "Mercadona c. ma", -12.40),
        ("20/09/2026", "Cafeteria plaza", -1.80),
        ("20/09/2026", "Cafeteria plaza", -1.80),  # dos cafés iguales el mismo día
        ("05/09/2026", "Recibo mes anterior", 55.30),
        ("28/08/2026", "Lidl ejemplo", -55.30),
    ]
    for i, (f, c, imp) in enumerate(filas):
        for col, v in zip("BCDEF", [f, TARJETA, c, imp, "€"]):
            ws[f"{col}{6 + i}"] = v
    wb.save(os.path.join(DIR, "bbva-tarjeta.xlsx"))


def ing_xls():
    """.xls binario de Excel 97-2003, como el que descarga ING."""
    import xlwt
    wb = xlwt.Workbook(encoding="utf-8"); ws = wb.add_sheet("Movimientos")
    fecha = xlwt.easyxf(num_format_str="dd/MM/yyyy")
    ws.write(0, 0, "Movimientos de la Cuenta"); ws.write(0, 2, "  Número de cuenta:"); ws.write(0, 3, "0000 0000 0000 00009999")
    ws.write(1, 2, "  Titular:"); ws.write(1, 3, "TITULAR FICTICIO")
    ws.write(2, 2, "  Fecha exportación:"); ws.write(2, 3, "29/10/2026 21:39h")
    for j, t in enumerate(["F. VALOR", "CATEGORÍA", "SUBCATEGORÍA", "DESCRIPCIÓN", "COMENTARIO", "IMPORTE (€)", "SALDO (€)"]):
        ws.write(3, j, t)
    filas = [  # más reciente primero
        (dt.date(2026, 10, 3), "Ventajas ING", "Otras Ventajas ING", "Incentivo por compra ING", 3.10),
        (dt.date(2026, 10, 3), "Vehículo y transporte", "Gasolina", "Compra ING GALP E S GALP EJEMPLO", -60.25),
        (dt.date(2026, 9, 1), "Otros ingresos", "Ingresos de otras entidades", "Transferencia recibida de TITULAR FICTICIO", 1000.00),
        (dt.date(2026, 8, 20), "Otros gastos", "Otros seguros", "Recibo MUTUA FICTICIA", -30.05),
    ]
    saldo = 1500.00
    for i, (f, cat, sub, desc, imp) in enumerate(filas):
        r = 4 + i
        ws.write(r, 0, f, fecha); ws.write(r, 1, cat); ws.write(r, 2, sub); ws.write(r, 3, desc)
        ws.write(r, 5, imp); ws.write(r, 6, round(saldo, 2))
        saldo = round(saldo - imp, 2)
    wb.save(os.path.join(DIR, "ing-cuenta.xls"))


bbva_tarjeta()
ing_xls()
print("Archivos de bancos generados")
