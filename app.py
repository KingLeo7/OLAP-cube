"""Flask web app: interactive OLAP cube explorer.

Run:  python app.py   ->  http://127.0.0.1:5000
"""
from flask import Flask, jsonify, render_template, request

import olap

app = Flask(__name__)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/meta")
def api_meta():
    return jsonify(olap.meta())


@app.get("/api/data")
def api_data():
    return jsonify(olap.CUBE.to_dict(orient="records"))


@app.post("/api/query")
def api_query():
    spec = request.get_json(silent=True)
    if not isinstance(spec, dict) or "rows" not in spec or "cols" not in spec:
        return jsonify(error="JSON body needs 'rows' and 'cols'"), 400
    try:
        return jsonify(olap.query(spec))
    except (ValueError, KeyError, TypeError) as exc:
        return jsonify(error=str(exc)), 400


if __name__ == "__main__":
    app.run(debug=True)
