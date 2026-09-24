#!/usr/bin/env python3
"""Inventory direct Earlgrey debug connections at a pinned revision."""
import hashlib
import json
from collections import Counter
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
    ('main', 'u_pinmux', 'pinmux_hw_debug_en_o', 'pinmux_pinmux_hw_debug_en'),
    ('main', 'u_pinmux', 'rv_jtag_o', 'pinmux_rv_jtag_req'),
    ('main', 'u_pinmux', 'rv_jtag_i', 'pinmux_rv_jtag_rsp'),
    ('main', 'u_rv_dm', 'lc_hw_debug_en_i', 'lc_ctrl_lc_hw_debug_en'),
    ('main', 'u_rv_dm', 'lc_hw_debug_clr_i', 'lc_ctrl_lc_hw_debug_clr'),
    ('main', 'u_rv_dm', 'pinmux_hw_debug_en_i', 'pinmux_pinmux_hw_debug_en'),
    ('main', 'u_rv_dm', 'jtag_i', 'pinmux_rv_jtag_req'),
    ('main', 'u_rv_dm', 'jtag_o', 'pinmux_rv_jtag_rsp'),
    ('main', 'u_csrng', 'lc_hw_debug_en_i', 'lc_ctrl_lc_hw_debug_en'),
    ('main', 'u_sram_ctrl_main', 'lc_hw_debug_en_i', 'lc_ctrl_lc_hw_debug_en'),
    ('main', 'u_sram_ctrl_sec', 'lc_hw_debug_en_i', 'lc_ctrl_lc_hw_debug_en'),
    ('top', 'earlgrey_pd_main', 'lc_ctrl_lc_hw_debug_en_o', 'lc_ctrl_lc_hw_debug_en'),
    ('top', 'earlgrey_pd_aon', 'lc_ctrl_lc_hw_debug_en_i', 'lc_ctrl_lc_hw_debug_en'),
    ('aon', 'u_pwrmgr', 'lc_hw_debug_en_i', 'lc_ctrl_lc_hw_debug_en_i'),
    ('aon', 'u_clkmgr', 'lc_hw_debug_en_i', 'lc_ctrl_lc_hw_debug_en_i'),
}
MODULES = {
    ('main', 'u_lc_ctrl'): 'lc_ctrl',
    ('main', 'u_pinmux'): 'pinmux',
    ('main', 'u_rv_dm'): 'rv_dm',
    ('main', 'u_csrng'): 'csrng',
    ('main', 'u_sram_ctrl_main'): 'sram_ctrl',
    ('main', 'u_sram_ctrl_sec'): 'sram_ctrl',
    ('top', 'earlgrey_pd_main'): 'earlgrey_pd_main',
    ('top', 'earlgrey_pd_aon'): 'earlgrey_pd_aon',
    ('aon', 'u_pwrmgr'): 'pwrmgr',
    ('aon', 'u_clkmgr'): 'clkmgr',
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


def parameter_contracts(texts):
    """Check only the pinned default and named forwarding for RV_DM mode."""
    contracts, unknown = [], []
    for name, module in [('top', 'top_earlgrey'), ('main', 'earlgrey_pd_main')]:
        clean = blank_comments(texts[name])
        headers = list(re.finditer(r'(?ms)^\s*module\s+' + module +
                                  r'\s*#\s*\((.*?)^\s*\)\s*\(', clean))
        declarations = (list(re.finditer(r'(?m)^\s*parameter\s+bit\s+RvDmUseDmiInterface\s*=\s*0\s*,',
                                        headers[0].group(1))) if len(headers) == 1 else [])
        names = (re.findall(r'(?m)^\s*parameter\b[^\n]*\bRvDmUseDmiInterface\b',
                            headers[0].group(1)) if len(headers) == 1 else [])
        if len(declarations) == len(names) == 1:
            line = clean.count('\n', 0, headers[0].start(1) + declarations[0].start()) + 1
            contracts.append(dict(file=FILES[name], line=line,
                                  contract='default RvDmUseDmiInterface = 0'))
        else:
            unknown.append(f'{name}: default RvDmUseDmiInterface = 0 not uniquely established')

    for name, module, instance, port in [('top', 'earlgrey_pd_main', 'earlgrey_pd_main',
                                         'RvDmUseDmiInterface'),
                                        ('main', 'rv_dm', 'u_rv_dm', 'UseDmiInterface')]:
        clean = blank_comments(texts[name])
        blocks = list(re.finditer(r'(?ms)^\s*' + module + r'\s*#\s*\((.*?)^\s*\)\s*' +
                                  instance + r'\s*\(', clean))
        pins = (list(re.finditer(r'(?m)^\s*\.' + port + r'\s*\(\s*RvDmUseDmiInterface\s*\)\s*,?\s*$',
                                 blocks[0].group(1))) if len(blocks) == 1 else [])
        names = (re.findall(r'\.' + port + r'\s*\(', blocks[0].group(1))
                 if len(blocks) == 1 else [])
        if len(pins) == len(names) == 1:
            line = clean.count('\n', 0, blocks[0].start(1) + pins[0].start()) + 1
            contracts.append(dict(file=FILES[name], line=line,
                                  contract=f'{instance}.{port} = RvDmUseDmiInterface'))
        else:
            unknown.append(f'{name}: {instance}.{port} forwarding not uniquely established')
    return contracts, unknown


def audit_texts(texts):
    """Audit the reviewed direct connections; report missing and added edges UNKNOWN."""
    found = {(name, edge[0], edge[1], edge[2]): edge[3] for name, text in texts.items()
             for edge in connections(text)
             if (name, edge[0], edge[1], edge[2]) in EXPECTED}
    missing = sorted(EXPECTED - found.keys())
    # Extra direct uses of these control nets extend the endpoint scope and need review.
    nets = {'lc_ctrl_lc_hw_debug_en', 'lc_ctrl_lc_hw_debug_clr',
            'lc_ctrl_lc_hw_debug_en_i', 'pinmux_pinmux_hw_debug_en',
            'pinmux_rv_jtag_req', 'pinmux_rv_jtag_rsp'}
    extra = sorted((name, *edge[:3]) for name, text in texts.items()
                   for edge in connections(text)
                   if edge[2] in nets and (name, *edge[:3]) not in EXPECTED)
    edges = [dict(file=FILES[name], line=line, instance=instance, port=port, net=net)
             for (name, instance, port, net), line in sorted(found.items())]
    unknown = [f'missing direct connection: {edge}' for edge in missing]
    unknown += [f'unreviewed direct connection: {edge}' for edge in extra]
    pin_counts = Counter()
    for name, text in texts.items():
        for block in re.finditer(r'(?ms)^\s*\)\s*(\w+)\s*\(\s*(.*?)^\s*\);',
                                 blank_comments(text)):
            pin_counts.update((name, block.group(1), port) for port in
                              re.findall(r'(?m)^\s*\.(\w+)\s*\(', block.group(2)))
    for name, instance, port, _ in sorted(EXPECTED):
        if pin_counts[name, instance, port] != 1:
            unknown.append(f'{name}: {instance}.{port} occurs {pin_counts[name, instance, port]} times')
    for name, text in texts.items():
        clean = blank_comments(text)
        for (file, instance), module in MODULES.items():
            if file != name:
                continue
            parameterized = re.findall(r'(?ms)^[ \t]*(\w+)[ \t]*#\s*\([^;]*?^\s*\)\s*' +
                                       instance + r'\s*\(', clean)
            plain = re.findall(r'(?m)^[ \t]*(\w+)\s+' + instance + r'\s*\(', clean)
            if (len(re.findall(r'\b' + re.escape(instance) + r'\s*\(', clean)) != 1 or
                    parameterized + plain != [module]):
                unknown.append(f'{name}: {instance} must be one {module} instance')
    contracts, parameter_unknown = parameter_contracts(texts)
    unknown += parameter_unknown
    return {'status': 'resolved_bounded' if not unknown else 'UNKNOWN',
            'edges': edges, 'contracts': contracts, 'unknown': unknown}


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
                  'scope': 'direct named-port debug connections and default RV_DM mode in Earlgrey top, main and AON wrappers',
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
