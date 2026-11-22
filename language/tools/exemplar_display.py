"""Display-only context windows for saved Exemplars and Clusters; evidence stays intact."""
from pathlib import Path
import re

HELPER = Path(__file__).with_suffix('.js')
MARKER = '// Exemplar display context:'

STYLE = '''<style id="example-fold-style">
.example-fold{margin:0 0 14px;border:0;padding:0}
.example-fold > summary{list-style:none;cursor:pointer}
.example-fold > summary::-webkit-details-marker{display:none}
.example-fold > summary .ex{margin-bottom:2px}
.example-toggle{display:block;margin-left:90px;font-size:12px;color:var(--ink3,#8b8b94)}
.example-toggle::before{content:'▸ ';font-size:11px}
.example-fold[open] > summary .ex{display:none}
.example-fold[open] .example-toggle::before{content:'▾ '}
.example-full .ex{margin-top:6px}
.example-full .ex{border-top:0}
#exemplars .example-fold .ex,#clusters .example-fold .ex{border:0}
#exemplars .example-fold + .example-fold,#clusters .example-fold + .example-fold{border-top:1px solid var(--rule2,#d9d9df);padding-top:14px}
.steering-table{width:100%;table-layout:fixed}
.steering-table th:first-child{width:65%}
.steering-table th,.steering-table td{padding-right:4px}
.steering-table th{overflow-wrap:anywhere}
.steering-table th:not(:first-child){text-align:right}
.steering-table td.num{width:auto}
.steering-table td.num .tile{min-width:0;padding:2px 4px;font-size:12px}
.steering-table .ex{grid-template-columns:64px minmax(0,1fr);font-size:13px;line-height:1.5}
.steering-table .example-fold{margin:0;padding:0;border:0}
.steering-table .example-toggle{margin-left:76px}
.steering-table .quiet{font-size:12px;line-height:1.4}
.steering-table .toks{overflow-wrap:anywhere;white-space:pre-wrap}
@media(max-width:620px){
  .steering-table th:first-child{width:52%}
  .steering-table td.num .tile{font-size:11px;padding:2px}
  .steering-table .ex{grid-template-columns:minmax(0,1fr);gap:2px}
  .steering-table .ex > .tile{justify-self:start}
  .steering-table .example-toggle{margin-left:0}
}
@media(max-width:390px){.steering-table th:first-child{width:44%}}
.graph-context{margin:8px 0 14px;font-size:14px;line-height:1.5}
.graph-context > summary{cursor:pointer}
.graph-context > summary .sub{display:block;margin:0 0 4px}
.graph-context[open] > summary .toks{display:none}
</style>'''


def install(source):
    """Make the shared folding helper and its styles available to report sections."""
    match = re.search(r'// 2\. Exemplars[^\n]*\n', source)
    if match is None:
        return source
    helper = HELPER.read_text(encoding='utf-8') + '\n'
    if MARKER in source:
        source = re.sub(r'// Exemplar display context:.*?(?=// 2\. Exemplars)',
                        lambda _: helper, source, count=1, flags=re.S)
    else:
        source = source[:match.start()] + helper + source[match.start():]
    source = re.sub(r'<style id="example-fold-style">.*?</style>', '', source, flags=re.S)
    head, separator, tail = source.partition('</head>')
    return head.rstrip() + '\n' + STYLE + '\n' + separator + tail if separator else source


def render(source):
    source = install(source)
    if MARKER not in source:
        return source
    start=source.find('// 1b. Activation spectrum')
    stop=source.find(MARKER,start)
    if start>=0 and stop>start:
        block=re.sub(
            r'exRow\((?:e|exemplarDisplay\(e, s, \d+\)), s, \(e.activation \|\| 0\) < 0, tileScale\)',
            'exRow(exemplarDisplay(e, s, 128), s, (e.activation || 0) < 0, tileScale)',
            source[start:stop])
        source=source[:start]+block+source[stop:]
    start = source.find('// 2. Exemplars')
    stop = source.find('// 3. Search', start)
    if stop < 0:
        return source
    block = source[start:stop]
    block = block.replace('e => exRow(e, s, neg, G)',
                          'e => foldedExample(e, s, neg, G)')
    block = block.replace('e => exRow(exemplarDisplay(e, s), s, neg, G)',
                          'e => foldedExample(e, s, neg, G)')
    source = source[:start] + block + source[stop:]
    source = source.replace(
        'const exList = (items, negPeak, tileScale) => {',
        'const exList = (items, negPeak, tileScale, displayWindow = false) => {')
    source = source.replace(
        'items.map(e => exRow(e, s, negPeak, tileScale))',
        'items.map(e => displayWindow ? foldedExample(e, s, negPeak, tileScale) : exRow(e, s, negPeak, tileScale))')
    source = source.replace(
        'items.map(e => exRow(displayWindow ? exemplarDisplay(e, s) : e, s, negPeak, tileScale))',
        'items.map(e => displayWindow ? foldedExample(e, s, negPeak, tileScale) : exRow(e, s, negPeak, tileScale))')
    source = source.replace(
        "exList(k.examples.slice(0, 3), poleOf(k) === 'negative', exScale)",
        "exList(k.examples.slice(0, 3), poleOf(k) === 'negative', exScale, true)")
    source = source.replace(
        'exList(r.examples.slice(0, 2))',
        'exList(r.examples.slice(0, 2), undefined, undefined, true)')
    return source
