# OLAP Cube Explorer (DWDM Academic Project)

**Student:** Rudra Prasad Rath | **Roll No.:** 202456115 | **Section:** AIML-A

An interactive web app (Python, Flask, pandas) that demonstrates the five OLAP operations
on a small sales data cube: **Roll-up, Drill-down, Slice, Dice and Pivot**.
It uses the same OdiMart sales data as the project report (grand total = Rs 671 lakh).

## Run

```bash
pip install -r requirements.txt
python app.py
# open http://127.0.0.1:5000
```

Run the tests: `python -m unittest discover -s tests -v`

## The cube

| Dimension | Hierarchy (coarse > fine) |
|-----------|---------------------------|
| Time      | year > quarter > month    |
| Location  | country > city            |
| Product   | category > item           |

Measure: `sales` (Rs lakh), aggregated with SUM. The fact table has 216 rows
(3 cities x 6 items x 12 months).

## How each operation works in the app

| Operation  | In the UI | In the code (`olap.py`) |
|------------|-----------|-------------------------|
| Roll-up    | **Roll** button moves a dimension up its hierarchy (down to *All* removes it) | `groupby` at a coarser level |
| Drill-down | **Drill** button moves a dimension to a finer level | `groupby` at a finer level |
| Slice      | Pick exactly one value of one column (e.g. quarter = Q4) | one `isin` filter |
| Dice       | Pick several values and/or several columns | several `isin` filters |
| Pivot      | Swap rows and columns, or choose a different dimension for each axis | `pivot_table(index, columns)` |

Each view also shows the equivalent **pandas** and **SQL** code, an operation log and the raw fact table.

## Files

```
app.py              Flask routes (/, /api/meta, /api/data, /api/query)
olap.py             cube builder + query engine
templates/index.html, static/app.js, static/style.css   front end
tests/test_olap.py  unit and API tests
```

## API

`POST /api/query`

```json
{"rows": {"dim": "location", "level": "city"},
 "cols": {"dim": "time", "level": "quarter"},
 "filters": {"quarter": ["Q4"]}}
```
