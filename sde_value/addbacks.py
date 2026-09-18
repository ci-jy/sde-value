"""Classify each claimed add-back and recommend whether a buyer should accept it.

The rules are deliberately simple so they can be written as the same live
formula in the workbook:

* owner compensation, non-cash (depreciation, amortisation) and financing
  (interest) keep their label; they are the standard SDE add-backs.
* a "one-time" item that showed up in two or more of the last three years is
  really recurring, and so is any item that would carry on under a new owner.
  Both become **recurring-disguised** and are rejected.
* a discretionary or one-time item with no documents behind it is rejected.
"""

from __future__ import annotations

from .deal import AddBack

STANDARD = ("owner compensation", "non-cash", "financing")


def classify(label: str, years_seen: int, continues: bool) -> str:
    if label in STANDARD:
        return label
    if continues or (label == "one-time" and years_seen >= 2):
        return "recurring-disguised"
    return label


def recommend(classification: str, documented: bool) -> bool:
    if classification == "recurring-disguised":
        return False
    if classification in ("discretionary", "one-time") and not documented:
        return False
    return True


def classify_addback(ab: AddBack) -> tuple[str, bool]:
    cls = classify(ab.label, ab.years_seen, ab.continues)
    return cls, recommend(cls, ab.documented)


def accepted(ab: AddBack) -> bool:
    """The buyer's toggle: an explicit override in the deal file, else the recommendation."""
    if ab.accept is not None:
        return bool(ab.accept)
    return classify_addback(ab)[1]


def rejection_reason(ab: AddBack) -> str | None:
    """Why the buyer's toggle is off for this add-back, in a sentence; None if accepted."""
    if accepted(ab):
        return None
    cls, recommended = classify_addback(ab)
    if recommended:
        reason = "Rejected by the buyer in the deal file"
    elif ab.continues:
        reason = "The cost carries on under a new owner"
    elif cls == "recurring-disguised":
        reason = f"Called one-time but it appears in {ab.years_seen} of the last 3 years"
    else:
        reason = f"No documents back up a {cls} expense"
    note = ab.note.strip()
    if note and note[-1] not in ".!?":
        note += "."
    return f"{reason}. {note}" if note else f"{reason}."
