#!/usr/bin/env python3
"""Build Northpoint Harbor assets for the MTA resource."""
from __future__ import annotations
import argparse
import json
from dataclasses import replace
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from citygen.config import DEFAULT_CONFIG
from citygen.pipeline import build_city


def main()->int:
    parser=argparse.ArgumentParser(description="Generate the deterministic Northpoint Harbor vertical slice")
    parser.add_argument("--output",type=Path,default=ROOT/"resource"/"fc_city",help="MTA resource output directory")
    parser.add_argument("--seed",type=int,default=DEFAULT_CONFIG.seed)
    parser.add_argument("--name",default=DEFAULT_CONFIG.name)
    parser.add_argument("--origin-x",type=float,default=DEFAULT_CONFIG.origin_x)
    parser.add_argument("--origin-y",type=float,default=DEFAULT_CONFIG.origin_y)
    parser.add_argument("--origin-z",type=float,default=DEFAULT_CONFIG.origin_z)
    parser.add_argument("--clean",action="store_true",help="remove files from the previous generated manifest before rebuilding")
    parser.add_argument("--reuse-generated",action="store_true",help="reuse existing DDS/TXD/audio while rebuilding models and JSON")
    args=parser.parse_args()
    config=replace(DEFAULT_CONFIG,name=args.name,seed=args.seed,origin_x=args.origin_x,
                   origin_y=args.origin_y,origin_z=args.origin_z)
    try:
        result=build_city(config,args.output,clean=args.clean,reuse_generated=args.reuse_generated)
    except Exception as exc:
        parser.exit(1,f"Build failed: {exc}\n")
    print(json.dumps(result,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
