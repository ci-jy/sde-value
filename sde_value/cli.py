"""Command line: build a workbook from a deal file, check it, or refresh data."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .deal import DealError, load_deal


def _money(x: float) -> str:
    return f"${x:,.0f}"


def cmd_build(args) -> int:
    from .engine import value_deal
    from .workbook import build_workbook

    deal = load_deal(args.deal)
    out = Path(args.out) if args.out else Path("out") / f"{deal.slug}.xlsx"
    build_workbook(deal, out)
    o = value_deal(deal)
    print(f"Wrote {out}")
    print(f"  {deal.name}")
    print(f"  Seller's SDE        {_money(o['seller_sde']):>12}   "
          f"(add-backs claimed {_money(o['claimed_total'])})")
    print(f"  Normalised SDE      {_money(o['normalised_sde']):>12}   "
          f"(rejected {_money(o['rejected_total'])})")
    print(f"  Owner replacement   {_money(o['replacement_cost']):>12}")
    print(f"  Normalised EBITDA   {_money(o['normalised_ebitda']):>12}")
    print(f"  Asking value        {_money(o['asking_value']):>12}   at {deal.asking_multiple:.1f}x")
    print(f"  Repriced value      {_money(o['repriced_value']):>12}   "
          f"({o['value_cut_pct']:.1%} below asking)")
    return 0


def cmd_check(args) -> int:
    from .check import check_workbook

    result = check_workbook(args.workbook, keep_dir=args.keep)
    for m in result.mismatches:
        print(f"MISMATCH {m.name}: workbook={m.workbook!r} engine={m.engine!r}")
    for name in result.missing:
        print(f"MISSING  {name}")
    status = "OK" if result.ok else "FAILED"
    print(f"{status}: {result.compared} output cells compared after LibreOffice recalculation, "
          f"{len(result.mismatches)} mismatches, {len(result.missing)} missing")
    return 0 if result.ok else 1


def cmd_fetch(args) -> int:
    from .fetch import refresh

    refresh()
    print("Refreshed data/ extracts")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="sde_value", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build", help="build the valuation workbook for a deal file")
    b.add_argument("--deal", required=True, help="deal YAML file")
    b.add_argument("--out", help="output .xlsx (default out/<deal>.xlsx)")
    b.set_defaults(func=cmd_build)
    c = sub.add_parser("check", help="recalculate in LibreOffice and compare with the engine")
    c.add_argument("workbook")
    c.add_argument("--keep", help="keep the recalculated copy in this directory")
    c.set_defaults(func=cmd_check)
    f = sub.add_parser("fetch-data", help="download BLS/SOI files and rebuild data/ extracts")
    f.set_defaults(func=cmd_fetch)
    args = p.parse_args(argv)
    try:
        return args.func(args)
    except DealError as exc:
        print(f"deal error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
