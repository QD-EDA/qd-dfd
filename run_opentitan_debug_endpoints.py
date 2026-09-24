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
    'rv_dm': 'hw/ip/rv_dm/rtl/rv_dm.sv',
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


def rv_dm_path_contracts(text):
    """Inventory the reviewed default JTAG-to-DMI source path, not its behavior."""
    clean = blank_comments(text)
    branches = list(re.finditer(
        r'\bif\s*\(\s*UseDmiInterface\s*\)\s*begin\s*:\s*gen_dmi_gating\b'
        r'.*?\bend\s+else\s+begin\s*:\s*gen_jtag_gating\b(.*?)^\s*end\s*$',
        clean, re.S | re.M))
    if (len(branches) != 1 or
            len(re.findall(r'\bbegin\s*:\s*gen_dmi_gating\b', clean)) != 1 or
            len(re.findall(r'\bbegin\s*:\s*gen_jtag_gating\b', clean)) != 1):
        return [], ['rv_dm: default gen_jtag_gating branch not uniquely established']
    branch = branches[0].group(1)
    offset = branches[0].start(1)
    guards = list(re.finditer(r'`ifndef\s+DMIDirectTAP\b(.*?)`endif', branch, re.S))
    if (len(guards) != 1 or re.search(r'^\s*`\w+', guards[0].group(1), re.M) or
            len(re.findall(r'\bdmi_jtag\s*#', clean)) != 1 or
            len(re.findall(r'\bdm_top\s*#', clean)) != 1):
        return [], ['rv_dm: default JTAG path DMIDirectTAP guard not uniquely established']
    guarded = guards[0].group(1)
    guard_offset = offset + guards[0].start(1)
    # Every pattern is a reviewed source contract. A duplicate or changed
    # expression is UNKNOWN; this deliberately does not elaborate SV.
    checks = [
        ('pinmux enable synchronizer', branch, offset,
         r'prim_lc_sync\s*#\s*\(\s*\.NumCopies\s*\(\s*int\s*\x27\s*\(\s*PmEnLastPos\s*\)\s*\)\s*\)\s*u_pm_en_sync\s*\(\s*\.clk_i\s*,\s*\.rst_ni\s*,\s*\.lc_en_i\s*\(\s*pinmux_hw_debug_en_i\s*\)\s*,\s*\.lc_en_o\s*\(\s*pinmux_hw_debug_en\s*\)\s*\)\s*;'),
        ('strict JTAG input gate', branch, offset,
         r'assign\s+jtag_in_int\s*=\s*\(\s*lc_tx_test_true_strict\s*\(\s*pinmux_hw_debug_en\s*\[\s*PmEnJtagIn\s*\]\s*\)\s*\)\s*\?\s*jtag_i\s*:\s*\x270\s*;'),
        ('strict JTAG output gate', branch, offset,
         r'assign\s+jtag_o\s*=\s*\(\s*lc_tx_test_true_strict\s*\(\s*pinmux_hw_debug_en\s*\[\s*PmEnJtagOut\s*\]\s*\)\s*\)\s*\?\s*jtag_out_int\s*:\s*\x270\s*;'),
        ('strict DMI enable', branch, offset,
         r'assign\s+dmi_en\s*=\s*lc_tx_test_true_strict\s*\(\s*pinmux_hw_debug_en\s*\[\s*PmEnDmiReq\s*\]\s*\)\s*;'),
        ('JTAG clock mux', guarded, guard_offset,
         r'prim_clock_mux2\s*#\s*\([^;]*?\)\s*u_prim_clock_mux2\s*\(\s*\.clk0_i\s*\(\s*jtag_in_int\.tck\s*\)\s*,\s*\.clk1_i\s*\(\s*clk_i\s*\)\s*,\s*\.sel_i\s*\(\s*testmode\s*\)\s*,\s*\.clk_o\s*\(\s*tck_muxed\s*\)\s*\)\s*;'),
        ('JTAG reset mux', guarded, guard_offset,
         r'prim_clock_mux2\s*#\s*\([^;]*?\)\s*u_prim_rst_n_mux2\s*\(\s*\.clk0_i\s*\(\s*jtag_in_int\.trst_n\s*\)\s*,\s*\.clk1_i\s*\(\s*scan_rst_ni\s*\)\s*,\s*\.sel_i\s*\(\s*testmode\s*\)\s*,\s*\.clk_o\s*\(\s*trst_n_muxed\s*\)\s*\)\s*;'),
        ('JTAG TAP ingress', guarded, guard_offset,
         r'dmi_jtag\s*#\s*\([^;]*?\)\s*dap\s*\([^;]*?\.tck_i\s*\(\s*tck_muxed\s*\)\s*,\s*\.tms_i\s*\(\s*jtag_in_int\.tms\s*\)\s*,\s*\.trst_ni\s*\(\s*trst_n_muxed\s*\)\s*,\s*\.td_i\s*\(\s*jtag_in_int\.tdi\s*\)\s*,[^;]*?\)\s*;'),
        ('JTAG TAP request connection', guarded, guard_offset,
         r'dmi_jtag\s*#\s*\([^;]*?\)\s*dap\s*\([^;]*?\.dmi_req_o\s*\(\s*dmi_req\s*\)\s*,[^;]*?\.dmi_req_valid_o\s*\(\s*dmi_req_valid_raw\s*\)\s*,[^;]*?\.dmi_req_ready_i\s*\(\s*dmi_req_ready\s*&\s*dmi_en\s*\)\s*,[^;]*?\)\s*;'),
        ('gated DMI request valid', guarded, guard_offset,
         r'assign\s+dmi_req_valid\s*=\s*dmi_req_valid_raw\s*&\s*dmi_en\s*;'),
        ('gated DMI response ready', guarded, guard_offset,
         r'assign\s+dmi_rsp_ready\s*=\s*dmi_rsp_ready_raw\s*&\s*dmi_en\s*;'),
        ('DMI request endpoint', clean, 0,
         r'dm_top\s*#\s*\([^;]*?\)\s*u_dm_top\s*\([^;]*?\.dmi_req_valid_i\s*\(\s*dmi_req_valid\s*\)\s*,\s*\.dmi_req_ready_o\s*\(\s*dmi_req_ready\s*\)\s*,\s*\.dmi_req_i\s*\(\s*dmi_req\s*\)\s*,[^;]*?\)\s*;'),
    ]
    anchors = {
        'pinmux enable synchronizer': r'\bu_pm_en_sync\s*\(',
        'strict JTAG input gate': r'\bassign\s+jtag_in_int\s*=',
        'strict JTAG output gate': r'\bassign\s+jtag_o\s*=',
        'strict DMI enable': r'\bassign\s+dmi_en\s*=',
        'JTAG clock mux': r'\bu_prim_clock_mux2\s*\(',
        'JTAG reset mux': r'\bu_prim_rst_n_mux2\s*\(',
        'JTAG TAP ingress': r'\bdap\s*\(',
        'JTAG TAP request connection': r'\bdap\s*\(',
        'gated DMI request valid': r'\bassign\s+dmi_req_valid\s*=',
        'gated DMI response ready': r'\bassign\s+dmi_rsp_ready\s*=',
        'DMI request endpoint': r'\bu_dm_top\s*\(',
    }
    contracts, unknown = [], []
    for label, source, start, pattern in checks:
        matches = list(re.finditer(pattern, source, re.S))
        anchors_found = list(re.finditer(anchors[label], source))
        if len(matches) != 1 or len(anchors_found) != 1:
            unknown.append(f'rv_dm: {label} has {len(matches)} reviewed forms and '
                           f'{len(anchors_found)} anchors')
        else:
            contracts.append({'file': FILES['rv_dm'],
                              'line': clean.count('\n', 0, start + matches[0].start()) + 1,
                              'contract': label})
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
    path_contracts, path_unknown = rv_dm_path_contracts(texts['rv_dm']) if 'rv_dm' in texts else ([], [])
    unknown += path_unknown
    return {'status': 'resolved_bounded' if not unknown else 'UNKNOWN',
            'edges': edges, 'contracts': contracts, 'rv_dm_path': path_contracts,
            'unknown': unknown}


def check_inputs_after(root, sources):
    """Retain post-scan input identity so a changed checkout cannot resolve."""
    observed = {'revision': None, 'git_status': None, 'sha256': {}}
    unknown = []
    try:
        observed['revision'] = subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
        observed['git_status'] = subprocess.check_output(
            ['git', 'status', '--porcelain'], cwd=root, text=True)
        for name, source in sources.items():
            observed['sha256'][name] = hashlib.sha256(
                (root / source['path']).read_bytes()).hexdigest()
    except (OSError, subprocess.SubprocessError) as error:
        observed['error'] = str(error)
        unknown.append(f'post-scan input check failed: {error}')
    if observed['revision'] != PIN:
        unknown.append('post-scan OpenTitan revision changed or could not be verified')
    if observed['git_status'] != '':
        unknown.append('post-scan OpenTitan checkout is dirty or could not be verified')
    for name, source in sources.items():
        if observed['sha256'].get(name) != source['sha256']:
            unknown.append(f'post-scan source changed or could not be verified: {source["path"]}')
    return observed, unknown


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
        postcheck, drift = check_inputs_after(root, sources)
        if drift:
            result['status'] = 'UNKNOWN'
            result['unknown'].extend(drift)
        report = {'schema_version': 1, 'opentitan_revision': revision,
                  'scope': 'reviewed direct Earlgrey wrapper connections and RV_DM default JTAG-to-DMI source contracts',
                  'assumptions': ['RvDmUseDmiInterface remains at its reviewed default 0',
                                  'DMIDirectTAP must be undefined for the guarded JTAG source path'],
                  'implementation_selection': 'UNKNOWN: external parameter overrides and preprocessor defines were not supplied',
                  'sources': sources, 'postcheck': postcheck, **result}
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
        print(f"{result['status']}: {len(result['edges'])} source-linked connections, "
              f"{len(result['rv_dm_path'])} conditional RV_DM contracts; "
              f"implementation selection UNKNOWN; report {report_path}")
        return 0 if result['status'] == 'resolved_bounded' else 2
    except (OSError, subprocess.SubprocessError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
