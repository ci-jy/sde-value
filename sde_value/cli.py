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
    print(f"  DCF value           {_money(o['dcf_value']):>12}   "
          f"({o['dcf_ebitda_multiple']:.1f}x normalised EBITDA)")
    print(f"  Largest financeable {_money(o['fin_max_price']):>12}   "
          f"(DSCR at asking {o['fin_asking_dscr']:.2f}x, needs {deal.loan.min_dscr:.2f}x)")
    print(f"  Supported value     {_money(o['supported_value']):>12}   "
          f"(capped at the {o['supported_basis']}; {o['financing_verdict']})")
    return 0


def cmd_check(args) -> int:
    from .check import RecalcError, check_workbook

    tabs = [t.strip() for t in args.tabs.split(",") if t.strip()] if args.tabs else None
    try:
        result = check_workbook(args.workbook, keep_dir=args.keep, tabs=tabs)
    except RecalcError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    for m in result.mismatches:
        print(f"MISMATCH {m.name}: workbook={m.workbook!r} engine={m.engine!r}")
    for name in result.missing:
        print(f"MISSING  {name}")
    status = "OK" if result.ok else "FAILED"
    where = f" on {', '.join(tabs)}" if tabs else ""
    print(f"{status}: {result.compared} output cells{where} compared after LibreOffice "
          f"recalculation, {len(result.mismatches)} mismatches, {len(result.missing)} missing")
    return 0 if result.ok else 1


def cmd_summary(args) -> int:
    from .engine import value_deal

    print(f"{'Deal':34} {'Seller SDE':>11} {'Norm. EBITDA':>12} {'Asking':>12} "
          f"{'Repriced':>12} {'Cut':>6}")
    cuts = []
    for path in args.deals:
        deal = load_deal(path)
        o = value_deal(deal)
        cuts.append(o["value_cut_pct"])
        print(f"{deal.name[:34]:34} {_money(o['seller_sde']):>11} "
              f"{_money(o['normalised_ebitda']):>12} {_money(o['asking_value']):>12} "
              f"{_money(o['repriced_value']):>12} {o['value_cut_pct']:>6.1%}")
    if cuts:
        print(f"Average cut across {len(cuts)} deals: {sum(cuts) / len(cuts):.1%}")
    return 0


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
    c.add_argument("--tabs", help="only compare cells on these tabs, e.g. DCF,Financing,Sensitivity")
    c.set_defaults(func=cmd_check)
    s = sub.add_parser("summary", help="print seller vs repriced value for several deals")
    s.add_argument("deals", nargs="+")
    s.set_defaults(func=cmd_summary)
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
