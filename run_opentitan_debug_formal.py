#!/usr/bin/env python3
"""Bounded selected-cone proof and independent simulation of SAT witnesses."""
import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys
import time


def main():
    if len(sys.argv) != 3:
        print('usage: run_opentitan_debug_formal.py OPENTITAN_ROOT EVIDENCE_DIR', file=sys.stderr)
        return 1
    root, out = [Path(p).resolve() for p in sys.argv[1:]]
    repo = Path(__file__).resolve().parent
    out.mkdir(parents=True, exist_ok=True)
    records = []
    try:
        pin = '7a3ad34b6d483f4d1d69ac670ddb1c45f1172e19'
        if (subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()!=pin or
                subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True)):
            raise ValueError('expected clean pinned OpenTitan checkout')
        paths = ['prim/rtl/prim_util_pkg.sv','prim/rtl/prim_mubi_pkg.sv',
                 'lc_ctrl/rtl/lc_ctrl_state_pkg.sv','lc_ctrl/rtl/lc_ctrl_reg_pkg.sv',
                 'lc_ctrl/rtl/lc_ctrl_pkg.sv','prim_generic/rtl/prim_flop.sv',
                 'prim/rtl/prim_sec_anchor_flop.sv','prim/rtl/prim_lc_sender.sv',
                 'lc_ctrl/rtl/lc_ctrl_signal_decode.sv']
        files = [root/'hw/ip'/p for p in paths]+[repo/'fixtures/opentitan_debug_formal.sv']
        include = root/'hw/ip/prim/rtl'
        def run(name, argv, expected_failure=False):
            start=time.monotonic()
            r=subprocess.run(argv,cwd=repo,capture_output=True,text=True,timeout=120)
            log=r.stdout+r.stderr; (out/(name+'.log')).write_text(log)
            records.append(dict(name=name,argv=argv,exit_status=r.returncode,seconds=time.monotonic()-start))
            if bool(r.returncode) != expected_failure or 'warning:' in log.lower():
                raise ValueError(name+': tool failure or warning; inspect raw log')
            return log
        run('yosys-version',['yosys','-V']);run('verilator-version',['verilator','--version'])
        inputs=files+list(include.glob('prim_assert*'))+[repo/'fixtures/opentitan_debug_replay.sv']
        (out/'inputs.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},indent=2))
        # read_slang keeps quote characters; this pilot accepts only simple paths.
        def quote(path):
            s=str(path)
            if not re.fullmatch(r'[A-Za-z0-9_./:+-]+',s):
                raise ValueError('pilot tool paths require letters, digits, _ . / : + -')
            return s
        for mode in ('proof','cover','invalid-cover','fault','clear-fault'):
            read='read_slang --top opentitan_debug_formal '+('-G BAD_GRANT=1 ' if mode=='fault' else '-G BAD_CLEAR=1 ' if mode=='clear-fault' else '')
            read+='-I'+quote(include)+' '+' '.join(map(quote,files))+'\n'
            script=read+'prep -top opentitan_debug_formal -flatten\nasync2sync\ndffunmap\ncheck -assert\n'
            script+='sat -seq 6 -set rst_ni 1 -set-at 1 rst_ni 0 -show-inputs -show-outputs '
            if mode in ('cover','invalid-cover'):
                # Pinned lc_ctrl_pkg: IdleSt=0x07ad, PostTransSt=0x6d2c; zero is invalid.
                script+='-set-at 3 fsm 1965 -set-at 4 fsm '+str(27948 if mode=='cover' else 0)+' '
                script+='-set-at 4 observed_debug 5 -set-at 5 observed_debug 10 -set-at 5 observed_clear 5 '
            else: script+='-prove bad 0 '+('-verify ' if mode=='proof' else '')
            if mode!='proof': script+='-dump_json '+quote(out/(mode+'.json'))
            path=out/(mode+'.ys');path.write_text(script+'\n')
            log=run(mode,['yosys','-Q','-s',str(path)])
            expected={'proof':'SAT proof finished - no model found: SUCCESS!',
                      'fault':'SAT proof finished - model found: FAIL!',
                      'clear-fault':'SAT proof finished - model found: FAIL!',
                      'cover':'SAT solving finished - model found:',
                      'invalid-cover':'SAT solving finished - model found:'}[mode]
            if expected not in log: raise ValueError(mode+': missing solver outcome')
            if mode=='proof': continue
            signals=json.loads((out/(mode+'.json')).read_text())['signal']
            values={}
            for signal in signals:
                if signal['name'] not in ('rst_ni','state_valid','dev','prod_end','secrets','fsm','observed_debug','observed_clear','bad'): continue
                data=iter(signal.get('data',[])); rows=[]; previous=None
                for symbol in signal['wave']:
                    if symbol in '=2345' and 'data' in signal: previous=next(data)
                    elif symbol!='.': previous=symbol
                    rows.append(previous)
                values[signal['name']]=rows[1:7] # index zero is unconstrained initial state
            keys=('rst_ni','state_valid','dev','prod_end','secrets','fsm','observed_debug','observed_clear','bad')
            widths=(1,1,1,1,4,16,4,4,1)
            rows=[]
            for i in range(6):
                row=''
                for key,width in zip(keys,widths):
                    bits=values[key][i]
                    if len(bits)!=width or any(b not in '01' for b in bits):
                        raise ValueError('unsupported witness value for '+key)
                    row+=bits
                rows.append(row)
            witness=out/(mode+'.mem');witness.write_text('\n'.join(rows)+'\n')
            obj=out/('obj-'+mode)
            run('build-'+mode,['verilator','--binary','--timing','--assert','--top-module','opentitan_debug_replay',
                '--timescale','1ns/1ps','--Mdir',str(obj),'-GBAD_GRANT='+str(int(mode=='fault')), '-GBAD_CLEAR='+str(int(mode=='clear-fault')),
                '-I'+str(include)]+list(map(str,files))+[str(repo/'fixtures/opentitan_debug_replay.sv')])
            log=run('replay-'+mode,[str(obj/'Vopentitan_debug_replay'),'+WITNESS='+str(witness)])
            if 'PASS: six-step witness replay' not in log: raise ValueError('missing replay completion')
            if mode=='cover':
                # Corrupt only the replay expectation, proving the comparator is active.
                wrong=out/'wrong.mem'
                changed=list(rows[0]); changed[-2]='1' if changed[-2]=='0' else '0'
                wrong.write_text(''.join(changed)+'\n'+'\n'.join(rows[1:])+'\n')
                log=run('reject-wrong-witness',[str(obj/'Vopentitan_debug_replay'),
                        '+WITNESS='+str(wrong)],expected_failure=True)
                if 'witness mismatch step 1:' not in log:
                    raise ValueError('negative replay did not fail at expected comparison')
        if subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True):
            raise ValueError('application tree changed')
        print('PASS: six-step scoped property, reachable On/Off with clear, and both injected counterexamples replayed; not signoff')
        return 0
    except (OSError,ValueError,KeyError,IndexError,StopIteration,subprocess.SubprocessError) as error:
        print(str(error),file=sys.stderr);return 1
    finally:
        (out/'commands.json').write_text(json.dumps(records,indent=2)+'\n')


if __name__=='__main__':
    raise SystemExit(main())
