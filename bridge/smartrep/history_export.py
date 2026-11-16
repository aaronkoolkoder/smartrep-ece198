"""Excel history download, using inline strings to keep user text literal."""
from io import BytesIO
import json
import re
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZIP_DEFLATED
from .db import connect

NS='http://schemas.openxmlformats.org/spreadsheetml/2006/main'


def column(index):
    result=''
    while index:
        index,remainder=divmod(index-1,26)
        result=chr(65+remainder)+result
    return result


def text(value):
    return escape(re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]','',str(value)))


def workbook(sheets):
    output=BytesIO()
    with ZipFile(output,'w',ZIP_DEFLATED) as archive:
        types=['<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
               '<Default Extension="xml" ContentType="application/xml"/>',
               '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
               '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>']
        archive.writestr('_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        book=[];rels=[]
        for i,(name,rows) in enumerate(sheets,1):
            types.append(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
            book.append(f'<sheet name="{name}" sheetId="{i}" r:id="rId{i}"/>')
            rels.append(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>')
            data=[]
            for row_index,row in enumerate(rows,1):
                cells=[]
                for c,value in enumerate(row,1):
                    style=' s="1"' if row_index==1 else ''
                    ref=f'{column(c)}{row_index}'
                    if isinstance(value,(int,float)):
                        cells.append(f'<c r="{ref}"{style}><v>{value}</v></c>')
                    else:
                        cells.append(f'<c r="{ref}" t="inlineStr"{style}><is><t xml:space="preserve">{text(value if value is not None else "")}</t></is></c>')
                data.append(f'<row r="{row_index}">'+''.join(cells)+'</row>')
            cols=len(rows[0])
            archive.writestr(f'xl/worksheets/sheet{i}.xml',f'<worksheet xmlns="{NS}"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols><col min="1" max="{cols}" width="23" customWidth="1"/></cols><sheetData>'+''.join(data)+f'</sheetData><autoFilter ref="A1:{column(cols)}{len(rows)}"/></worksheet>')
        rels.append(f'<Relationship Id="rId{len(sheets)+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>')
        archive.writestr('xl/styles.xml',f'<styleSheet xmlns="{NS}"><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF24634F"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="2"><xf fontId="0" fillId="0" borderId="0" xfId="0"/><xf fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>')
        archive.writestr('xl/workbook.xml',f'<workbook xmlns="{NS}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'+''.join(book)+'</sheets></workbook>')
        archive.writestr('xl/_rels/workbook.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+''.join(rels)+'</Relationships>')
        archive.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'+''.join(types)+'</Types>')
    return output.getvalue()


def export_history(path,participant):
    with connect(path) as db:
        person=db.execute('SELECT * FROM participants WHERE id=?',(participant,)).fetchone()
        if not person:
            return None
        sets=[dict(row) for row in db.execute('SELECT s.*,e.name AS exercise_name FROM sets s JOIN exercises e ON e.id=s.exercise_id WHERE s.participant_id=? ORDER BY s.started_at,s.id',(participant,))]
        reps=[dict(row) for row in db.execute('SELECT r.*,s.exercise_id,s.started_at AS set_started_at FROM reps r JOIN sets s ON s.id=r.set_id WHERE s.participant_id=? ORDER BY s.started_at,r.set_id,r.idx',(participant,))]
        calibration=[dict(row) for row in db.execute('SELECT * FROM calibration_runs WHERE participant_id=? ORDER BY id',(participant,))]
        samples=[dict(row) for row in db.execute('SELECT * FROM motion_samples WHERE participant_id=? ORDER BY id',(participant,))]
    def table(records,headers):
        return [headers]+[[record.get(key) for key in headers] for record in records]
    notes=[['Patient ID','Name','Export coverage'],[person['id'],person['display_name'],'All saved exercise history. Graph recording starts with this update; earlier graph inputs were not stored. Times are UTC. Diagnostic inputs are not validated exercise data.']]
    sample_keys=sorted({key for row in samples for key in json.loads(row['channels_json'])})
    graph_headers=['captured_at','exercise_id','phase','run_id','sample_ms','units','normalized','diagnostic',*sample_keys]
    for row in samples:
        row.update(json.loads(row['channels_json']))
    return workbook([
        ('Patient',notes),
        ('Sets',table(sets,['id','exercise_name','station_id','started_at','ended_at','set_number','load_lb','reps_completed','good','short','rushed','end_reason'])),
        ('Reps',table(reps,['set_id','exercise_id','set_started_at','idx','quality','peak_p','rom','duration_s','t_start_ms'])),
        ('Graph data',table(samples,graph_headers)),
        ('Calibration',table(calibration,['id','exercise_id','device_id','started_at','ended_at','status','result_json']))])
