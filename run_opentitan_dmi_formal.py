#!/usr/bin/env python3
"""Bounded retained DMI permission checks using the real pinned gate and primitives."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import platform
import shutil
import subprocess
import sys
import time

import yaml
from edalize.icarus import Icarus


def main():
    if len(sys.argv) != 3:
        print('usage: run_opentitan_dmi_formal.py OPENTITAN_ROOT NEW_EVIDENCE_DIR', file=sys.stderr)
        return 1
    root, out = [Path(p).resolve() for p in sys.argv[1:]]
    repo = Path(__file__).resolve().parent
    records = []
    replay_unknown = []
    try:
        out.mkdir(parents=True)
        if any(not re.fullmatch(r'[A-Za-z0-9_./-]+', str(p)) for p in (root,out,repo)):
            raise ValueError('tool paths must contain only letters, digits, _ . / -')
        if subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip() != '7a3ad34b6d483f4d1d69ac670ddb1c45f1172e19':
            raise ValueError('wrong OpenTitan pin')
        if subprocess.check_output(['git','status','--porcelain'],cwd=root):
            raise ValueError('OpenTitan must be clean')
        for package, version in [('fusesoc','2.4.5'),('edalize','0.6.3')]:
            if importlib.metadata.version(package) != version:
                raise ValueError('required '+package+'=='+version)

        def run(name, argv, cwd=repo, fail=False, inspect_failure=False):
            start=time.monotonic()
            p=subprocess.run(argv,cwd=cwd,capture_output=True,text=True,timeout=120)
            log=p.stdout+p.stderr
            (out/(name+'.log')).write_text(log)
            records.append(dict(name=name,argv=argv,cwd=str(cwd),exit_status=p.returncode,seconds=time.monotonic()-start))
            (out/'commands.json').write_text(json.dumps(records,indent=2)+'\n')
            if bool(p.returncode) != fail and not inspect_failure:
                raise ValueError(name+': unexpected exit; inspect raw log')
            return log

        (out/'environment.json').write_text(json.dumps({
            'platform':platform.platform(), 'python':sys.version,
            'tool_executables':{tool:{'path':str(Path(shutil.which(tool)).resolve()),
                'sha256':hashlib.sha256(Path(shutil.which(tool)).resolve().read_bytes()).hexdigest()}
                for tool in ('fusesoc','yosys','verilator') if shutil.which(tool)},
            'packages':{p:importlib.metadata.version(p) for p in ('fusesoc','edalize','PyYAML')}
        },indent=2)+'\n')
        for tool in ('fusesoc','yosys','verilator'):
            run(tool+'-version',[tool,'-V' if tool=='yosys' else '--version'])
        log=run('resolve',['fusesoc','--cores-root='+str(root),'run',
            '--mapping=lowrisc:prim_generic:all:0.1','--mapping=lowrisc:systems:top_earlgrey:0.1',
            '--target=default','--tool=icarus','--setup','--build-root='+str(out/'build'),
            'lowrisc:ip:rv_dm:0.1'])
        if 'Non-deterministic selection' in log:
            raise ValueError('ambiguous core mapping')
        manifests=list((out/'build').rglob('*.eda.yml'))
        if len(manifests)!=1: raise ValueError('expected one EDAM')
        manifest=manifests[0];data=yaml.safe_load(manifest.read_text())
        if data['parameters'] or data['tool_options'] != {'icarus':{}}:
            raise ValueError('unexpected build options')
        sources, includes=Icarus(data,work_root=str(manifest.parent))._get_fileset_files()
        files=[(manifest.parent/f.name).resolve() for f in sources]
        inc=[(manifest.parent/p).resolve() for p in includes]
        files.append(repo/'fixtures/opentitan_dmi_formal.sv')
        replay=repo/'fixtures/opentitan_dmi_replay.sv'
        inputs=[(manifest.parent/f['name']).resolve() for f in data['files']]+files[-1:]+[replay,Path(__file__).resolve()]
        (out/'inputs.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},indent=2)+'\n')
        binaries={}
        for mode in ('proof','clear_debug','bypass','escalate','fault'):
            fault=mode=='fault'
            script='read_slang --top opentitan_dmi_formal '+('-G BAD_GRANT=1 ' if fault else '')
            script+=' '.join('-I'+str(p) for p in inc)+' '+' '.join(map(str,files))+'\n'
            script+='prep -top opentitan_dmi_formal -flatten\nasync2sync\ndffunmap\ncheck -assert\n'
            script+='sat -seq 10 -set rst_ni 1 -set-at 1 rst_ni 0 -show-inputs -show-outputs '
            if mode in ('proof','fault'):
                script+='-prove bad 0 '+('-verify ' if mode=='proof' else '')
            else:
                script+='-set strap 0 -set-at 4 strap 1 -set enable 10 -set-at 2 enable 5 -set-at 3 enable 5 '
                script+='-set clear_debug 10 -set bypass 10 -set escalate 10 '
                for step in (6,7,8): script+=f'-set-at {step} {mode} 0 '
                script+='-set-at 5 observed_enable 1 -set-at 6 observed_enable 1 -set-at 9 observed_enable 0 '
            if mode!='proof': script+='-dump_json '+str(out/(mode+'.json'))
            path=out/(mode+'.ys');path.write_text(script+'\n')
            log=run(mode,['yosys','-Q','-s',str(path)])
            expected=('SAT proof finished - no model found: SUCCESS!' if mode=='proof' else
                      'SAT proof finished - model found: FAIL!' if fault else 'SAT solving finished - model found:')
            if expected not in log or 'warning:' in log.lower(): raise ValueError(mode+': unexpected solver result or warning')
            if mode=='proof': continue
            keys=('rst_ni','strap','enable','clear_debug','bypass','escalate','observed_enable','bad')
            widths=(1,1,4,4,4,4,1,1)
            values={}
            for signal in json.loads((out/(mode+'.json')).read_text())['signal']:
                if signal['name'] not in keys: continue
                data_values=iter(signal.get('data',[]));rows=[];previous=None
                for symbol in signal['wave']:
                    if symbol in '=2345' and 'data' in signal: previous=next(data_values)
                    elif symbol!='.': previous=symbol
                    rows.append(previous)
                values[signal['name']]=rows[1:11]
            rows=[]
            for i in range(10):
                row=''
                for key,width in zip(keys,widths):
                    bits=values[key][i]
                    if len(bits)!=width or any(b not in '01' for b in bits): raise ValueError('nonbinary witness')
                    row+=bits
                rows.append(row)
            witness=out/(mode+'.mem');witness.write_text('\n'.join(rows)+'\n')
            if fault not in binaries:
                obj=out/('obj-fault' if fault else 'obj-normal')
                log=run('build-'+mode,['verilator','--binary','--timing','--assert','--top-module','opentitan_dmi_replay',
                    '--timescale','1ns/1ps','--Mdir',str(obj),'-GBAD_GRANT='+str(int(fault))]+
                    ['-I'+str(p) for p in inc]+list(map(str,files))+[str(replay)],inspect_failure=True)
                if records[-1]['exit_status']:
                    if (records[-1]['exit_status'] != 1 or log.count('%Warning-') != 1 or
                            '%Warning-UNOPTFLAT:' not in log or 'tlul_lc_gate.sv:69:' not in log or
                            '%Error: Exiting due to 1 warning(s)' not in log or log.count('%Error:') != 1):
                        raise ValueError('unrecognized replay build failure')
                    binaries[fault]=None
                else:
                    binaries[fault]=str(obj/'Vopentitan_dmi_replay')
                if not records[-1]['exit_status'] and ('warning:' in log.lower() or '%warning' in log.lower()): raise ValueError('simulator warnings')
            if binaries[fault] is None:
                replay_unknown.append(mode)
                continue
            log=run('replay-'+mode,[binaries[fault],'+WITNESS='+str(witness)])
            if 'PASS: ten-step DMI permission witness replay' not in log: raise ValueError('missing replay completion')
            if mode=='clear_debug':
                wrong=out/'wrong.mem';changed=list(rows[0]);changed[-2]='1' if changed[-2]=='0' else '0'
                wrong.write_text(''.join(changed)+'\n'+'\n'.join(rows[1:])+'\n')
                log=run('reject-wrong-witness',[binaries[fault],'+WITNESS='+str(wrong)],fail=True)
                if 'witness mismatch step 1:' not in log: raise ValueError('wrong negative failure')
        if subprocess.check_output(['git','status','--porcelain'],cwd=root): raise ValueError('application changed')
        (out/'summary.json').write_text(json.dumps({
            'qualification':'UNKNOWN', 'bounded_property':'no counterexample in 10 steps',
            'replay_unknown':replay_unknown, 'all_witnesses_replayed':not replay_unknown,
            'remaining_scope':['TL-UL traffic', 'live TAP gating', 'analog CDC', 'four-state behavior',
                               'test-chip strap override', 'full lifecycle integration']},indent=2)+'\n')
        if replay_unknown:
            print('UNKNOWN: bounded property checked; Verilator UNOPTFLAT blocks independent replay')
            return 2
        print('PASS: ten-step retained DMI permission property and four witness replays; qualification UNKNOWN')
        return 0
    except (OSError,ValueError,KeyError,IndexError,StopIteration,subprocess.SubprocessError) as e:
        print(str(e),file=sys.stderr);return 1


if __name__=='__main__':
    raise SystemExit(main())
