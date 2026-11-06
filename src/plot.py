"""Render the checked-in scenario results with ReportLab charts."""
import csv
import json
from pathlib import Path
from reportlab.graphics.shapes import Drawing, String
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics import renderPDF
from reportlab.lib import colors
import pypdfium2 as pdfium

ROOT = Path(__file__).resolve().parents[1]


def plot():
    summaries = json.loads((ROOT/'reports/summary.json').read_text())
    with (ROOT/'reports/base_monthly.csv').open() as f:
        months = list(csv.DictReader(f))
    d = Drawing(1000, 400)
    navy, blue, red = map(colors.HexColor, ['#172b4d', '#2563eb', '#b42318'])
    d.add(String(28, 369, 'NEWTON PARK  /  B2B PILOT ECONOMICS', fontName='Helvetica-Bold', fontSize=20, fillColor=navy))
    d.add(String(28, 344, 'Educational assumptions. RUB million. Expected values, not actual sales.', fontSize=11, fillColor=colors.HexColor('#526275')))
    bar = VerticalBarChart(); bar.x=68; bar.y=83; bar.width=370; bar.height=205
    bar.data = [[s['operating_result_rub']/1e6 for s in summaries]]
    bar.categoryAxis.categoryNames = ['Base', 'Downside', 'Upside']
    bar.valueAxis.valueMin = min(-1, min(bar.data[0])-1)
    bar.valueAxis.valueMax = max(1, max(bar.data[0])+1)
    bar.bars[0].fillColor=blue; bar.bars[0].strokeColor=blue
    bar.categoryAxis.joinAxisMode='bottom'
    bar.categoryAxis.labels.fontName='Helvetica';bar.valueAxis.labels.fontName='Helvetica';bar.barLabels.fontName='Helvetica'
    bar.valueAxis.visibleGrid=True; bar.valueAxis.gridStrokeColor=colors.HexColor('#e5e7eb')
    bar.barLabelFormat='%.2f'; bar.barLabels.fontSize=10
    d.add(bar); d.add(String(68,310,'Operating result',fontName='Helvetica-Bold',fontSize=13,fillColor=navy))
    line=HorizontalLineChart(); line.x=560; line.y=83; line.width=400; line.height=205
    line.data=[[float(r['closing_cash_rub'])/1e6 for r in months], [0.0]*len(months)]
    line.categoryAxis.categoryNames=[r['month'][5:] for r in months]
    line.categoryAxis.joinAxisMode='bottom'
    line.categoryAxis.labels.fontName='Helvetica';line.valueAxis.labels.fontName='Helvetica'
    line.valueAxis.visibleGrid=True; line.valueAxis.gridStrokeColor=colors.HexColor('#e5e7eb')
    values=line.data[0]
    line.valueAxis.valueMin=min(-1,min(values)-0.2);line.valueAxis.valueMax=max(4,max(values)+0.2)
    line.lines[0].strokeColor=blue;line.lines[0].strokeWidth=2
    line.lines[1].strokeColor=red;line.lines[1].strokeWidth=1;line.lines[1].strokeDashArray=[4,3]
    d.add(line);d.add(String(560,310,'Base: closing cash with RUB 4m opening balance',fontName='Helvetica-Bold',fontSize=12,fillColor=navy))
    d.add(String(560,55,'Months: May 2025 to April 2026',fontSize=10,fillColor=navy))
    base=summaries[0]
    d.add(String(28,22,f"Minimum opening funding: RUB {base['minimum_opening_cash_rub']/1e6:.3f}m  |  No extra liquidity buffer included",fontSize=11,fillColor=navy))
    pdf=pdfium.PdfDocument(renderPDF.drawToString(d))
    pdf[0].render(scale=1.6).to_pil().save(ROOT/'reports/economics.png')
    pdf.close()


if __name__=='__main__':
    plot()
