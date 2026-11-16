#!/usr/bin/env python3
"""Annotation bench — click a box on the page, decide if it is evidence.

    streamlit run app.py --server.headless true

Three tabs: the parsed pages with boxes, the accepted evidence, and a question
builder. Clicking a box opens that unit's crop and its accept/delete controls on
the right; there is no separate review list.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pymupdf
import streamlit as st
from streamlit_image_coordinates import streamlit_image_coordinates

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from finrag import annotations  # noqa: E402
from finrag.agent_rag import Tools, run as run_agent, score_answer  # noqa: E402
from finrag.llm import DeepSeekClient  # noqa: E402
from finrag.vectors import UnitIndex  # noqa: E402
from finrag.ingest import load_cache, parse_pdf, save_cache  # noqa: E402
from finrag.overlay import overlay_page  # noqa: E402
from finrag.ui import crop_region, nearest_unit  # noqa: E402

ANNOT = ROOT / "annotations"
UNITS_PATH = ANNOT / "units.jsonl"
QUESTIONS_PATH = ANNOT / "questions.jsonl"
CACHE = ANNOT / "cache"
UPLOADS = ANNOT / "uploads"
for path in (ANNOT, CACHE, UPLOADS):
    path.mkdir(parents=True, exist_ok=True)

DPI = 100
st.set_page_config(page_title="Citation units", page_icon="🔎", layout="wide")


def page_height(pdf_path: Path, page: int) -> float:
    with pymupdf.open(pdf_path) as doc:
        return doc[page - 1].rect.height


@st.cache_resource
def load_reranker():
    """Cross-encoder used by the winning retrieval arm; loaded once per process."""
    try:
        from sentence_transformers import CrossEncoder
        return CrossEncoder("BAAI/bge-reranker-base")
    except Exception:
        return None


def semantic_index(pool):
    """Load an embedding index only if it covers the units being searched."""
    npz = sorted(Path("annotations/vectors").rglob("*.npz"),
                 key=lambda p: p.stat().st_mtime)
    if not npz:
        return None, "no index built"
    index = UnitIndex.load(npz[-1])
    covered = len(set(index.unit_ids) & {u.unit_id for u in pool})
    if covered == 0:
        return None, ("the stored index does not cover these units — rebuild it "
                      "with scripts/vector_eval.py")
    return index, f"semantic index covers {covered}/{len(pool)} units"


def accepted_index() -> dict[str, dict]:
    return {r["unit_id"]: r for r in annotations.read_all(UNITS_PATH)}


# ==========================================================================
# Sidebar
# ==========================================================================
with st.sidebar:
    st.title("Document")
    uploaded = st.file_uploader("Upload a financial report (PDF)", type="pdf")
    start_page = st.number_input("First page", 1, 500, 1)
    n_pages = st.slider("Pages to parse", 1, 40, 1)
    end_page = start_page + n_pages - 1

    st.divider()
    show_builder = st.checkbox("Show question builder", value=False,
                               help="Hidden by default: questions are written in "
                                    "annotations/questions_*.jsonl for now.")
    st.text_input("DeepSeek API key", type="password", key="api_key",
                  help="Used only for the Ask tab, held in this session, never written "
                       "to disk. Leave empty to disable asking.")
    st.divider()
    st.caption(f"units accepted: {len(annotations.read_all(UNITS_PATH))}\n\n"
               f"questions: {len(annotations.read_all(QUESTIONS_PATH))}")

    with st.expander("Reset evidence"):
        st.caption("Archives `units.jsonl` and `questions.jsonl` to "
                   "`annotations/archive/<timestamp>/`. Nothing is deleted.")
        confirmed = st.checkbox("Start the annotation set again", key="reset-confirm")
        if st.button("Reset evidence", disabled=not confirmed, key="reset-button"):
            dest = annotations.archive_files([UNITS_PATH, QUESTIONS_PATH],
                                             ANNOT / "archive")
            st.success(f"archived to {dest.relative_to(ROOT)}")
            st.rerun()

if uploaded is None:
    st.title("Citation units")
    st.info("Upload a PDF. Docling proposes what is on the page; you decide what "
            "counts as evidence. Nothing leaves this machine.")
    st.stop()

data = uploaded.getvalue()
digest = hashlib.sha1(data).hexdigest()[:10]
pdf_path = UPLOADS / f"{digest}_{uploaded.name}"
if not pdf_path.exists():
    pdf_path.write_bytes(data)

state_key = f"units:{digest}:{start_page}-{end_page}"
if state_key not in st.session_state:
    cached = load_cache(CACHE, pdf_path, start_page, end_page)
    if cached is None:
        bar = st.progress(0.0, text=f"Parsing pages {start_page}–{end_page}…")
        started = time.time()

        def on_page(done: int, total: int) -> None:
            elapsed = time.time() - started
            eta = (elapsed / done) * (total - done) if done else 0.0
            bar.progress(done / total,
                         text=f"Page {start_page + done - 1} of {end_page} · "
                              f"{elapsed:.0f}s elapsed · ~{eta:.0f}s left")

        units = parse_pdf(pdf_path, start=start_page, end=end_page, progress=on_page)
        bar.empty()
        save_cache(CACHE, pdf_path, units, start_page, end_page)
    else:
        units = cached
    st.session_state[state_key] = units
units = st.session_state[state_key]

accepted = accepted_index()
pages = sorted({u.page for u in units})

_tabs = ["Page boxes", "Accepted evidence"]
if show_builder:
    _tabs.append("Build a question")
_tabs.append("Ask")
tab_boxes, tab_accepted, *rest = st.tabs(_tabs)
tab_ask = rest.pop()
tab_questions = rest[0] if rest else None

# ==========================================================================
# Page boxes — click to select
# ==========================================================================
with tab_boxes:
    head = st.columns([2, 1, 2])
    page_no = head[0].selectbox("Page", pages, index=0)
    head[1].caption(f"{len(units)} units\n\n{len(accepted)} accepted")
    page_units = [u for u in units if u.page == page_no]

    left, right = st.columns([2, 1])
    with left:
        st.caption("Click a box to see what it contains. Green = table row, "
                   "blue = text, orange = figure.")
        selected_now = st.session_state.get("selected")
        key = f"overlay:{digest}:{page_no}:{selected_now}"
        if key not in st.session_state:
            st.session_state[key] = overlay_page(
                pdf_path, page_no, units, set(accepted), dpi=DPI,
                label_mode="none", highlight=selected_now)
        image = st.session_state[key]
        click = streamlit_image_coordinates(image, key=f"click:{digest}:{page_no}",
                                            width=720)
        if click:
            scale = image.width / click.get("width", image.width)
            x = click["x"] * scale * 72.0 / DPI
            y = page_height(pdf_path, page_no) - click["y"] * scale * 72.0 / DPI
            hit = nearest_unit(page_units, x, y)
            new_id = hit.unit_id if hit else None
            if new_id != st.session_state.get("selected"):
                st.session_state["selected"] = new_id
                st.rerun()      # redraw with the highlight; guarded to avoid a loop

    with right:
        selected_id = st.session_state.get("selected")
        unit = next((u for u in page_units if u.unit_id == selected_id), None)
        if unit is None:
            st.info("Nothing selected yet.")
        else:
            st.markdown(f"**p{unit.page} · {unit.channel}**  \n`{unit.unit_id}`")
            try:
                st.image(crop_region(pdf_path.parent, pdf_path.name, unit.page,
                                     unit.bbox, dpi=150), width="stretch")
            except Exception as exc:
                st.warning(f"crop failed: {exc}")
            st.code(unit.quote[:500], language=None)
            nums = ", ".join(f"{n:g}" for n in unit.numbers) or "—"
            st.caption(f"numbers: {nums}" + (f" · ⚠️ {unit.value_flag}"
                                             if unit.value_flag else ""))
            chosen = unit.value
            if len(unit.numbers) > 1:
                chosen = st.selectbox("Number to cite", unit.numbers,
                                      key=f"n-{unit.unit_id}")

            if unit.unit_id in accepted:
                st.success(f"accepted — value {accepted[unit.unit_id].get('value')}")
                if st.button("Delete from evidence", key=f"d-{unit.unit_id}"):
                    annotations.delete_unit(UNITS_PATH, unit.unit_id)
                    st.rerun()
            elif st.button("Accept as evidence", type="primary",
                           key=f"a-{unit.unit_id}"):
                annotations.accept_unit(UNITS_PATH,
                                        {**unit.as_dict(), "value": chosen})
                st.rerun()

# ==========================================================================
# Accepted evidence
# ==========================================================================
with tab_accepted:
    rows = annotations.read_all(UNITS_PATH)
    if not rows:
        st.info("No evidence accepted yet. Click a box on a page and accept it.")
    else:
        st.caption(f"{len(rows)} units, {sum(1 for r in rows if r.get('value') is not None)} "
                   f"with a value.")
        by_id = {u.unit_id: u for u in units}
        for row in rows:
            unit = by_id.get(row["unit_id"])
            with st.expander(f"{row['unit_id']} · p{row['page']} · "
                             f"{row.get('channel')} · value {row.get('value')}"):
                cols = st.columns([1, 2, 1])
                with cols[0]:
                    if unit:
                        try:
                            st.image(crop_region(pdf_path.parent, pdf_path.name,
                                                 unit.page, unit.bbox, dpi=120),
                                     width="stretch")
                        except Exception:
                            st.caption("crop unavailable")
                with cols[1]:
                    st.code((row.get("quote") or "")[:400], language=None)
                    st.caption(f"numbers: {row.get('numbers')}")
                with cols[2]:
                    if st.button("Delete", key=f"del-{row['unit_id']}"):
                        annotations.delete_unit(UNITS_PATH, row["unit_id"])
                        st.rerun()
        st.download_button("Download units.jsonl", UNITS_PATH.read_text(),
                           "units.jsonl")

# ==========================================================================
# Build a question
# ==========================================================================
with (tab_questions if tab_questions is not None else st.container()):
    rows = annotations.read_all(UNITS_PATH) if tab_questions is not None else []
    if tab_questions is None:
        pass
    elif not rows:
        st.info("Accept at least one unit first.")
    else:
        options = {f"{r['unit_id']} — p{r['page']}: {r['quote'][:70]}": r["unit_id"]
                   for r in rows}
        picked = st.multiselect("Required units", list(options))
        question = st.text_input("Question", "What was the Group's net profit in 2024?")
        picked_ids = [options[k] for k in picked]
        default_gold = next((r["value"] for r in rows
                             if r["unit_id"] in picked_ids
                             and r.get("value") is not None), 0.0)
        gold = st.number_input("Gold value", value=float(default_gold or 0.0),
                               format="%f")
        if st.button("Append question", type="primary"):
            existing = {r.get("qid") for r in annotations.read_all(QUESTIONS_PATH)}
            n = len(existing) + 1
            qid = f"Q{n:03d}"
            while qid in existing:
                n += 1
                qid = f"Q{n:03d}"
            annotations.add_question(QUESTIONS_PATH, qid, question, gold,
                                     picked_ids, pdf_path.name)
            st.success(f"{qid} appended")
        st.download_button("Download questions.jsonl",
                           QUESTIONS_PATH.read_text() if QUESTIONS_PATH.exists() else "",
                           "questions.jsonl")

# ==========================================================================
# Ask — the agent
# ==========================================================================
with tab_ask:
    st.subheader("Ask the document")
    st.caption("The model chooses tools and writes the answer. Every number in "
               "that answer must appear in one of the quotes it cites, or the "
               "answer is withheld.")

    pool_choice = st.radio("Search over", ["Accepted evidence", "All parsed units"],
                           horizontal=True)
    accepted_units = [u for u in units if u.unit_id in accepted]
    pool = accepted_units if pool_choice == "Accepted evidence" else list(units)

    question = st.text_input("Question", "What was the Group's net profit in 2024?",
                             key="ask-question")

    api_key = st.session_state.get("api_key", "")
    if not pool:
        st.info("No accepted evidence yet — accept a unit, or switch to all parsed units.")
    elif not api_key:
        st.info("Add a DeepSeek API key in the sidebar to ask. The rest of the app "
                "works without one.")
    elif st.button("Ask", type="primary", key="ask-button"):
        with st.spinner(f"Asking over {len(pool)} units…"):
            try:
                client = DeepSeekClient(api_key=api_key)
                vector_index, note = semantic_index(pool)
                st.session_state["ask-index-note"] = note
                started = time.perf_counter()
                result = run_agent(question, client,
                                   Tools(pool, vector_index=vector_index,
                                         reranker=load_reranker()))
                result["latency_ms"] = round((time.perf_counter() - started) * 1000, 1)
                result["outcome"] = score_answer(result, None)
                st.session_state["ask-result"] = result

                runs = ANNOT / "runs"
                runs.mkdir(parents=True, exist_ok=True)
                record = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                          "model": client.model, "question": question,
                          "answer": result["answer"], "citations": result["citations"],
                          "verification": result["verification"], "trace": result["trace"],
                          "tool_calls": result["tool_calls"],
                          "latency_ms": result["latency_ms"], "outcome": result["outcome"]}
                with (runs / f"{datetime.now(timezone.utc):%Y%m%d}.jsonl").open("a") as fh:
                    fh.write(json.dumps(record, sort_keys=True) + "\n")
            except Exception as exc:  # pragma: no cover - network path
                st.error(f"agent failed: {exc}")

    result = st.session_state.get("ask-result")
    if result:
        note = st.session_state.get("ask-index-note")
        if note:
            st.caption(note + f" · {result.get('latency_ms', 0):.0f} ms")
        verdict = result["verification"]
        (st.success if verdict["accepted"] else st.warning)(
            f"{verdict['status']}" + (f" — {verdict['failures']}" if verdict["failures"] else ""))
        st.markdown(f"**{result['answer'] or '(no answer)'}**")

        lookup = {u.unit_id: u for u in units}
        cited = [lookup[c] for c in result["citations"] if c in lookup]
        if cited:
            st.caption(f"{len(cited)} citation(s)")
        for unit in cited:
            left, right = st.columns([1, 2])
            with left:
                try:
                    st.image(crop_region(pdf_path.parent, pdf_path.name, unit.page,
                                         unit.bbox, dpi=130), width="stretch")
                except Exception:
                    st.caption("crop unavailable")
            with right:
                tag = "accepted evidence" if unit.unit_id in accepted else "not accepted"
                st.markdown(f"`{unit.unit_id}` · p{unit.page} · {tag}")
                st.code(unit.quote[:300], language=None)

        if result["trace"]:
            st.caption("Tool calls")
            st.dataframe([{"tool": step["tool"], "returned": step["returned"],
                           "args": str(step["args"])[:80]} for step in result["trace"]],
                         width="stretch", hide_index=True)
