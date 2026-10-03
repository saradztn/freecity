#!/usr/bin/env python3
"""Validate source/build outputs and MTA resource references."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from citygen.validator import validate_resource


def main()->int:
    parser=argparse.ArgumentParser(description="Run static and binary checks for an MTA city resource")
    parser.add_argument("resource",nargs="?",type=Path,default=ROOT/"resource"/"fc_city")
    args=parser.parse_args()
    result=validate_resource(args.resource)
    print(json.dumps(result,indent=2))
    return 0 if result["ok"] else 1


if __name__=="__main__":
    raise SystemExit(main())
