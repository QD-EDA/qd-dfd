#!/usr/bin/env python3
"""Inventory direct Earlgrey lc_hw_debug_en/clr connections at a pinned revision."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

PIN = '7a3ad34b6d483f4d1d69ac670ddb1c45f1172e19'
FILES = {
    'top': 'hw/top_earlgrey/rtl/autogen/top_earlgrey.sv',
    'main': 'hw/top_earlgrey/rtl/autogen/earlgrey_pd_main.sv',
    'aon': 'hw/top_earlgrey/rtl/autogen/earlgrey_pd_aon.sv',
}
EXPECTED = {
    ('main', 'u_lc_ctrl', 'lc_hw_debug_en_o', 'lc_ctrl_lc_hw_debug_en'),
    ('main', 'u_lc_ctrl', 'lc_hw_debug_clr_o', 'lc_ctrl_lc_hw_debug_clr'),
    ('main', 'u_pinmux', 'lc_hw_debug_en_i', 'lc_ctrl_lc_hw_debug_en'),
    ('main', 'u_pinmux', 'lc_hw_debug_clr_i', 'lc_ctrl_lc_hw_debug_clr'),
    ('main', 'u_rv_dm', 'lc_hw_debug_en_i', 'lc_ctrl_lc_hw_debug_en'),
    ('main', 'u_rv_dm', 'lc_hw_debug_clr_i', 'lc_ctrl_lc_hw_debug_clr'),
    ('main', 'u_csrng', 'lc_hw_debug_en_i', 'lc_ctrl_lc_hw_debug_en'),
    ('main', 'u_sram_ctrl_main', 'lc_hw_debug_en_i', 'lc_ctrl_lc_hw_debug_en'),
    ('main', 'u_sram_ctrl_sec', 'lc_hw_debug_en_i', 'lc_ctrl_lc_hw_debug_en'),
    ('top', 'earlgrey_pd_main', 'lc_ctrl_lc_hw_debug_en_o', 'lc_ctrl_lc_hw_debug_en'),
    ('top', 'earlgrey_pd_aon', 'lc_ctrl_lc_hw_debug_en_i', 'lc_ctrl_lc_hw_debug_en'),
    ('aon', 'u_pwrmgr', 'lc_hw_debug_en_i', 'lc_ctrl_lc_hw_debug_en_i'),
    ('aon', 'u_clkmgr', 'lc_hw_debug_en_i', 'lc_ctrl_lc_hw_debug_en_i'),
}


def blank_comments(text):
    """Remove SV comments while retaining newlines for source coordinates."""
    return re.sub(r'/\*.*?\*/|//[^\n]*',
                  lambda match: re.sub(r'[^\n]', ' ', match.group()), text,
                  flags=re.S)


def connections(text):
    """Return simple named instance-pin connections; expressions stay bounded."""
    clean = blank_comments(text)
    result = []
    block = re.compile(r'(?m)^\s*\)\s*(\w+)\s*\(\s*(.*?)^\s*\);', re.S)
    pin = re.compile(r'(?m)^\s*\.(\w+)\s*\(\s*([^()\n]+?)\s*\)\s*,?\s*$')
    for instance in block.finditer(clean):
        for match in pin.finditer(instance.group(2)):
            result.append((instance.group(1), match.group(1), match.group(2).strip(),
                           clean.count('\n', 0, instance.start(2) + match.start()) + 1))
    return result


def audit_texts(texts):
    """Audit the reviewed direct connections; report missing and added edges UNKNOWN."""
    found = {(name, edge[0], edge[1], edge[2]): edge[3] for name, text in texts.items()
             for edge in connections(text)
             if (name, edge[0], edge[1], edge[2]) in EXPECTED}
    missing = sorted(EXPECTED - found.keys())
    # Extra direct uses of these control nets extend the endpoint scope and need review.
    nets = {'lc_ctrl_lc_hw_debug_en', 'lc_ctrl_lc_hw_debug_clr',
            'lc_ctrl_lc_hw_debug_en_i'}
    extra = sorted((name, *edge[:3]) for name, text in texts.items()
                   for edge in connections(text)
                   if edge[2] in nets and (name, *edge[:3]) not in EXPECTED)
    edges = [dict(file=FILES[name], line=line, instance=instance, port=port, net=net)
             for (name, instance, port, net), line in sorted(found.items())]
    unknown = [f'missing direct connection: {edge}' for edge in missing]
    unknown += [f'unreviewed direct connection: {edge}' for edge in extra]
    return {'status': 'resolved_bounded' if not unknown else 'UNKNOWN',
            'edges': edges, 'unknown': unknown}


def main():
    if len(sys.argv) != 3:
        print('usage: run_opentitan_debug_endpoints.py OPENTITAN_ROOT EVIDENCE_JSON', file=sys.stderr)
        return 2
    root, report_path = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    try:
        revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
        if revision != PIN or subprocess.check_output(['git', 'status', '--porcelain'], cwd=root, text=True):
            raise ValueError('expected clean pinned OpenTitan checkout')
        if report_path == root or root in report_path.parents:
            raise ValueError('evidence report must be outside the OpenTitan checkout')
        raw = {name: (root / path).read_bytes() for name, path in FILES.items()}
        texts = {name: data.decode('utf-8') for name, data in raw.items()}
        result = audit_texts(texts)
        sources = {name: {'path': path, 'sha256': hashlib.sha256(raw[name]).hexdigest()}
                   for name, path in FILES.items()}
        report = {'schema_version': 1, 'opentitan_revision': revision,
                  'scope': 'direct named-port connections for lc_hw_debug_en/clr in Earlgrey top, main and AON wrappers',
                  'sources': sources, **result}
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
        print(f"{result['status']}: {len(result['edges'])} source-linked connections; report {report_path}")
        return 0 if result['status'] == 'resolved_bounded' else 2
    except (OSError, subprocess.SubprocessError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
