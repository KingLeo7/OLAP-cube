"""OLAP engine: builds a small sales data cube and answers cube queries.

Dimensions and their concept hierarchies (coarse -> fine):
    time     : year > quarter > month
    location : country > city
    product  : category > item
Measure: sales (Rs lakh), aggregated with SUM.

The quarterly sales of the 3 cities x 3 categories are the same OdiMart figures
used in the DWDM report; they are split into months and items deterministically
(integer arithmetic in tenths), so every roll-up still matches the report totals.
"""
import pandas as pd

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

CATEGORIES = {
    "Electronics": ["Phones", "Laptops"],
    "Clothing": ["Men", "Women"],
    "Grocery": ["Staples", "Snacks"],
}

# (city, category) -> sales (Rs lakh) for Q1..Q4 of 2025
BASE = {
    ("Bhubaneswar", "Electronics"): [20, 25, 30, 35],
    ("Bhubaneswar", "Clothing"): [12, 15, 18, 22],
    ("Bhubaneswar", "Grocery"): [30, 32, 34, 38],
    ("Cuttack", "Electronics"): [14, 16, 19, 21],
    ("Cuttack", "Clothing"): [10, 11, 13, 16],
    ("Cuttack", "Grocery"): [22, 24, 25, 28],
    ("Puri", "Electronics"): [8, 9, 11, 12],
    ("Puri", "Clothing"): [6, 7, 9, 12],
    ("Puri", "Grocery"): [15, 16, 17, 19],
}

DIMS = {
    "time": {"label": "Time", "levels": ["year", "quarter", "month"]},
    "location": {"label": "Location", "levels": ["country", "city"]},
    "product": {"label": "Product", "levels": ["category", "item"]},
}
LEVEL_TO_DIM = {lvl: d for d, spec in DIMS.items() for lvl in spec["levels"]}
ITEM_ORDER = [i for items in CATEGORIES.values() for i in items]


def build_cube() -> pd.DataFrame:
    rows = []
    for (city, cat), quarters in BASE.items():
        for qi, value in enumerate(quarters):
            v10 = value * 10  # work in tenths of a lakh -> exact integers
            m1 = round(v10 * 0.30)
            m2 = round(v10 * 0.33)
            months10 = [m1, m2, v10 - m1 - m2]
            for mi, m10 in enumerate(months10):
                i1 = round(m10 * 0.6)
                for item, val10 in zip(CATEGORIES[cat], [i1, m10 - i1]):
                    rows.append({
                        "country": "India", "city": city,
                        "category": cat, "item": item,
                        "year": "2025", "quarter": f"Q{qi + 1}",
                        "month": MONTH_NAMES[qi * 3 + mi],
                        "sales": val10 / 10,
                    })
    return pd.DataFrame(rows)


CUBE = build_cube()


def ordered(col, values):
    """Return values of a level in their natural order."""
    values = list(dict.fromkeys(values))
    if col == "month":
        return sorted(values, key=MONTH_NAMES.index)
    if col == "item":
        return sorted(values, key=ITEM_ORDER.index)
    if col == "category":
        return sorted(values, key=list(CATEGORIES).index)
    return sorted(values)


def meta():
    return {
        "dims": DIMS,
        "values": {c: ordered(c, CUBE[c].unique()) for c in LEVEL_TO_DIM},
        "level_to_dim": LEVEL_TO_DIM,
        "facts": len(CUBE),
        "total": round(float(CUBE["sales"].sum()), 1),
    }


def _axis_level(axis):
    dim, level = axis.get("dim"), axis.get("level")
    if dim not in DIMS:
        raise ValueError(f"unknown dimension: {dim!r}")
    if level == "all":
        return dim, None
    if level not in DIMS[dim]["levels"]:
        raise ValueError(f"level {level!r} is not in dimension {dim!r}")
    return dim, level


def _describe(spec, rdim, rlvl, cdim, clvl, filters):
    """List which OLAP operations the current view represents."""
    ops = []
    on_axes = {rdim, cdim}
    for dim, lvl in ((rdim, rlvl), (cdim, clvl)):
        levels = DIMS[dim]["levels"]
        label = DIMS[dim]["label"]
        if lvl is None:
            ops.append(("rollup", f"Roll-up: {label} removed (collapsed to All)"))
        elif lvl != levels[-1]:
            ops.append(("rollup", f"Roll-up: {label} shown at {lvl} level "
                                  f"(drill-down possible to {levels[levels.index(lvl) + 1]})"))
    for dim in DIMS:
        if dim not in on_axes:
            ops.append(("rollup", f"Roll-up: {DIMS[dim]['label']} aggregated away (not on an axis)"))
    n_cols = len(filters)
    n_vals = sum(len(v) for v in filters.values())
    if n_cols == 1 and n_vals == 1:
        col, vals = next(iter(filters.items()))
        ops.append(("slice", f"Slice: {col} = {vals[0]!r}"))
    elif n_cols:
        parts = " AND ".join(f"{c} in {v}" for c, v in filters.items())
        ops.append(("dice", f"Dice: {parts}"))
    ops.append(("pivot", f"Pivot: rows = {DIMS[rdim]['label']}, columns = {DIMS[cdim]['label']}"))
    return [{"type": t, "text": x} for t, x in ops]


def _code(rlvl, clvl, filters):
    py = ['df = cube.copy()  # fact table: country, city, category, item, year, quarter, month, sales']
    sql_where = []
    for col, vals in filters.items():
        kind = "SLICE" if len(filters) == 1 and len(vals) == 1 else "DICE"
        py.append(f'df = df[df["{col}"].isin({vals!r})]  # {kind}')
        sql_where.append(f"{col} IN ({', '.join(repr(v) for v in vals)})")
    if rlvl and clvl:
        py.append(f'pd.pivot_table(df, values="sales", index="{rlvl}", columns="{clvl}",\n'
                  f'               aggfunc="sum", margins=True)  # ROLL-UP / PIVOT')
    elif rlvl or clvl:
        py.append(f'df.groupby("{rlvl or clvl}")["sales"].sum()  # ROLL-UP')
    else:
        py.append('df["sales"].sum()  # fully rolled up')
    group = [x for x in (rlvl, clvl) if x]
    sql = "SELECT " + "".join(f"{g}, " for g in group) + "SUM(sales) AS sales\nFROM sales_cube"
    if sql_where:
        sql += "\nWHERE " + "\n  AND ".join(sql_where)
    if group:
        sql += "\nGROUP BY " + ", ".join(group)
    return "\n".join(py), sql + ";"


def query(spec):
    """spec = {rows:{dim,level}, cols:{dim,level}, filters:{column:[values]}}"""
    rdim, rlvl = _axis_level(spec["rows"])
    cdim, clvl = _axis_level(spec["cols"])
    if rdim == cdim:
        raise ValueError("rows and columns must use different dimensions")
    filters = {}
    df = CUBE
    for col, vals in (spec.get("filters") or {}).items():
        if col not in LEVEL_TO_DIM:
            raise ValueError(f"unknown column: {col!r}")
        if vals:
            filters[col] = [str(v) for v in vals]
            df = df[df[col].isin(filters[col])]

    d = df.assign(_r=df[rlvl] if rlvl else "All", _c=df[clvl] if clvl else "All")
    pt = d.pivot_table(index="_r", columns="_c", values="sales", aggfunc="sum", fill_value=0)
    rows = ordered(rlvl, pt.index) if rlvl else ["All"]
    cols = ordered(clvl, pt.columns) if clvl else ["All"]
    if len(pt):
        pt = pt.reindex(index=rows, columns=cols, fill_value=0)
        matrix = [[round(float(v), 1) for v in r] for r in pt.values]
    else:
        rows, cols, matrix = [], [], []
    row_tot = [round(sum(r), 1) for r in matrix]
    col_tot = [round(sum(c), 1) for c in zip(*matrix)] if matrix else []
    pandas_code, sql = _code(rlvl, clvl, filters)
    return {
        "row_label": rlvl or "All", "col_label": clvl or "All",
        "rows": rows, "cols": cols, "matrix": matrix,
        "row_totals": row_tot, "col_totals": col_tot,
        "grand": round(sum(row_tot), 1),
        "ops": _describe(spec, rdim, rlvl, cdim, clvl, filters),
        "pandas": pandas_code, "sql": sql,
        "cells_used": int(len(df)),
    }
