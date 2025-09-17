import inspect
import json
import os
import re
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

# Import the FastAPI app
from main import app  # type: ignore


def _get_summary_from_doc(doc: Optional[str]) -> str:
	if not doc:
		return ""
	summary = doc.strip().splitlines()[0].strip()
	return summary


def _is_protected(route: Any) -> bool:
	dependant = getattr(route, "dependant", None)
	return bool(dependant and getattr(dependant, "dependencies", []))


def _is_admin_only(route: Any) -> bool:
	dependant = getattr(route, "dependant", None)
	if not dependant:
		return False
	for dep in getattr(dependant, "dependencies", []) or []:
		call = getattr(dep, "call", None)
		name = getattr(call, "__name__", "") if call else ""
		if name.startswith("get_current_admin_user"):
			return True
	return False


def _collect_route_info(route: Any) -> Dict[str, Any]:
	methods = sorted(m for m in (getattr(route, "methods", set()) or set()) if m not in {"HEAD", "OPTIONS"})
	path = getattr(route, "path", getattr(route, "path_format", ""))
	name = getattr(route, "name", "") or ""
	endpoint = getattr(route, "endpoint", None)
	doc = inspect.getdoc(endpoint) if endpoint else None
	summary = _get_summary_from_doc(doc or getattr(endpoint, "__doc__", "") if endpoint else "")
	response_model = getattr(route, "response_model", None)
	response_model_name = getattr(response_model, "__name__", None) if response_model else None

	return {
		"methods": methods,
		"path": path,
		"name": name,
		"summary": summary,
		"protected": _is_protected(route),
		"admin_only": _is_admin_only(route),
		"response_model": response_model_name,
	}


def _as_pytest_html_data(routes: List[Dict[str, Any]]) -> Dict[str, Any]:
	# Build an environment summary similar to pytest-html
	env = {
		"Python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
		"Platform": os.name,
		"Packages": {"fastapi": "", "starlette": ""},
		"Plugins": {},
	}

	# Map each endpoint to a single-row "test"
	tests: Dict[str, List[Dict[str, Any]]] = {}
	for r in routes:
		if not r["methods"]:
			continue
		label = f"{','.join(r['methods'])} {r['path']}"
		desc_parts = []
		if r["summary"]:
			desc_parts.append(r["summary"])
		if r["response_model"]:
			desc_parts.append(f"-> {r['response_model']}")
		badge = "Admin" if r["admin_only"] else ("Protected" if r["protected"] else "Open")
		desc_parts.append(f"[{badge}]")
		desc = " ".join(desc_parts)

		row = [
			"<td class=\"col-result\">Passed</td>",
			f"<td class=\"col-testId\">{label}</td>",
			"<td class=\"col-duration\">-</td>",
			"<td class=\"col-links\"></td>",
		]
		entry = {
			"extras": [],
			"result": "Passed",
			"testId": label,
			"duration": "-",
			"resultsTableRow": row,
			"log": desc or "",
		}
		tests[label] = [entry]

	return {
		"environment": env,
		"tests": tests,
		"renderCollapsed": ["passed"],
		"initialSort": "result",
		"title": "report_apis.html",
	}


def _html_escape_quotes_for_data_attr(s: str) -> str:
	# Match style used in report_teachers.html (&#34; for ")
	return s.replace('"', "&#34;")


def _clone_template_and_fill(data: Dict[str, Any], target_path: str) -> None:
	with open("report_teachers.html", "r", encoding="utf-8") as f:
		tmpl = f.read()

	# Replace title tag text
	tmpl = re.sub(r"<title[^>]*>.*?</title>", "<title id=\"head-title\">report_apis.html</title>", tmpl, flags=re.DOTALL)
	# Replace H1 visible title
	tmpl = re.sub(r"<h1 id=\"title\">.*?</h1>", "<h1 id=\"title\">report_apis.html</h1>", tmpl, flags=re.DOTALL)
	# Replace run-count line to mention endpoints
	count = len(data.get("tests", {}))
	run_count_re = re.compile(r"<p class=\"run-count\">.*?</p>")
	tmpl = run_count_re.sub(f"<p class=\"run-count\">{count} endpoints listed.</p>", tmpl)

	# Prepare JSON blob and inject into data-container attribute
	json_blob = json.dumps(data)
	json_blob_attr = _html_escape_quotes_for_data_attr(json_blob)
	tmpl = re.sub(r"(<div id=\"data-container\" data-jsonblob=\").*?(\"></div>)", r"\1" + json_blob_attr + r"\2", tmpl, flags=re.DOTALL)

	with open(target_path, "w", encoding="utf-8") as f:
		f.write(tmpl)


def main() -> None:
	# Collect routes
	routes: List[Dict[str, Any]] = []
	for route in getattr(app, "routes", []) or []:
		path = getattr(route, "path", getattr(route, "path_format", ""))
		if path in {"/openapi.json", "/docs", "/redoc"}:
			continue
		if not getattr(route, "methods", None):
			continue
		info = _collect_route_info(route)
		routes.append(info)

	routes.sort(key=lambda r: (r["path"], ",".join(r["methods"])) )

	# Build pytest-html-like data object
	data = _as_pytest_html_data(routes)

	# Render into a clone of report_teachers.html
	_target = "report_apis.html"
	_clone_template_and_fill(data, _target)
	print(f"{_target} generated with {len(routes)} endpoints on {datetime.now().strftime('%d-%b-%Y at %H:%M:%S')}")


if __name__ == "__main__":
	main()
