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
