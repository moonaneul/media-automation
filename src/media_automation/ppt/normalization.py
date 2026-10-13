"""Normalize imported Office layout IDs and XML property order on output copies."""
from pathlib import Path
from pptx.oxml.ns import qn

def normalize_layout_ids(file):
    """Layout IDs share one presentation-wide namespace, including copied masters."""
    from zipfile import ZipFile, ZIP_DEFLATED
    from lxml import etree as E
    with ZipFile(file) as z:parts={n:z.read(n) for n in z.namelist()}
    presentation=E.fromstring(parts['ppt/presentation.xml'])
    number=2147483647
    for node in presentation.iter(qn('p:sldMasterId')):number+=1;node.set('id',str(number))
    parts['ppt/presentation.xml']=E.tostring(presentation,encoding='UTF-8',xml_declaration=True,standalone=True)
    for name in parts:
        if name.startswith('ppt/slideMasters/') and name.endswith('.xml'):
            root=E.fromstring(parts[name])
            for node in root.iter(qn('p:sldLayoutId')):number+=1;node.set('id',str(number))
            parts[name]=E.tostring(root,encoding='UTF-8',xml_declaration=True,standalone=True)
    # Some edited references contain appended font fills after typefaces, or two
    # colors inside solidFill. Office repairs these even though renderers accept them.
    order=['ln','noFill','solidFill','gradFill','blipFill','pattFill','grpFill','effectLst','effectDag','highlight','uLnTx','uLn','uFillTx','uFill','latin','ea','cs','sym','hlinkClick','hlinkMouseOver','rtl','extLst']
    fill_tags={'noFill','solidFill','gradFill','blipFill','pattFill','grpFill'}
    color_tags={'scrgbClr','srgbClr','hslClr','sysClr','schemeClr','prstClr'}
    for name,blob in list(parts.items()):
        if not name.startswith('ppt/') or not name.endswith('.xml'):continue
        root=E.fromstring(blob);changed=False
        for fill in root.iter(qn('a:solidFill')):
            colors=[c for c in fill if E.QName(c).localname in color_tags]
            for extra in colors[1:]:fill.remove(extra);changed=True
        for props in root.iter():
            if props.tag not in (qn('a:rPr'),qn('a:defRPr'),qn('a:endParaRPr')):continue
            fills=[c for c in props if E.QName(c).localname in fill_tags]
            for extra in fills[1:]:props.remove(extra);changed=True
            children=list(props)
            sorted_children=sorted(children,key=lambda c:order.index(E.QName(c).localname) if E.QName(c).localname in order else len(order))
            if children!=sorted_children:
                for child in children:props.remove(child)
                for child in sorted_children:props.append(child)
                changed=True
        if changed:parts[name]=E.tostring(root,encoding='UTF-8',xml_declaration=True,standalone=True)
    target=Path(str(file)+'.normalized')
    with ZipFile(target,'w',ZIP_DEFLATED) as z:
        for name,blob in parts.items():z.writestr(name,blob)
    target.replace(file)
