#!/usr/bin/env python3
"""Decide whether to dispatch another free all-photo reverse search run.

Never dispatch on an incomplete/invalid checkpoint or unproductive execution.
This follows verified durable checkpoints only; no API calls or media here.
"""
import argparse
import json
from pathlib import Path


def decide(states, step, max_steps=64):
    if type(step) is not int or step<0 or type(max_steps) is not int or max_steps<1:
        raise ValueError('INVALID_CAMPAIGN_STEP')
    if set(states)!= {'mimmi','yui'}:
        raise ValueError('INCOMPLETE_CAMPAIGN_MODELS')
    summary={}
    for model,state in states.items():
        if (state.get('schema_version')!=1 or state.get('model')!=model
                or type(state.get('last_cycle_size')) is not int
                or state['last_cycle_size']<=0
                or not isinstance(state.get('attempted_ids'), list)
                or type(state.get('last_run_attempts')) is not int
                or state['last_run_attempts']<0):
            raise ValueError('INVALID_CAMPAIGN_CHECKPOINT_'+model)
        total=state['last_cycle_size']
        unique=len(set(state['attempted_ids']))
        if unique!=len(state['attempted_ids']) or unique>total:
            raise ValueError('CORRUPT_CAMPAIGN_COVERAGE_'+model)
        pending = state.get('retry_pending_ids', [])
        unverified = state.get('unverified_after_retry_ids', [])
        if (not isinstance(pending, list) or len(pending)!=len(set(pending))
                or not isinstance(unverified, list) or len(unverified)!=len(set(unverified))
                or set(pending)-set(state['attempted_ids']) or
                set(pending)&set(unverified)):
            raise ValueError('CORRUPT_REVERSE_RETRY_STATE_'+model)
        summary[model]={'total':total,'attempted':unique,
                        'remaining':total-unique+len(pending),
                        'pending_retry':len(pending),
                        'unverified_after_retry':len(unverified),
                        'last_run_attempts':state['last_run_attempts']}
    unfinished=any(v['remaining']>0 for v in summary.values())
    progressed=any(v['last_run_attempts']>0 for v in summary.values())
    within_budget=step<max_steps
    return {'dispatch':unfinished and progressed and within_budget,
            'all_attempted':not unfinished,
            'no_progress':unfinished and not progressed,
            'max_steps_reached':unfinished and not within_budget,
            'next_step':step+1,'models':summary}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--mimmi',required=True,type=Path)
    p.add_argument('--yui',required=True,type=Path)
    p.add_argument('--step',type=int,required=True)
    p.add_argument('--max-steps',type=int,default=64)
    p.add_argument('--github-output',type=Path)
    a=p.parse_args()
    result=decide({m:json.loads(getattr(a,m).read_text()) for m in ('mimmi','yui')},
                  a.step,a.max_steps)
    print('GALLERY_FULL_REVERSE_CAMPAIGN_PROGRESS',json.dumps(result,sort_keys=True),flush=True)
    if a.github_output:
        with a.github_output.open('a') as f:
            f.write(f"dispatch={'true' if result['dispatch'] else 'false'}\n")
            f.write(f"next_step={result['next_step']}\n")
            f.write(f"all_attempted={'true' if result['all_attempted'] else 'false'}\n")


if __name__=='__main__':
    main()
