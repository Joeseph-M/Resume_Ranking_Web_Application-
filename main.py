from __future__ import annotations 

import io #Manage raw file bytes in memory instead of saving the resumes in disk 
import math 
import os 
import re 
import shutil #Allow parsing for file operations 
import subprocess # Allow CLI utlity for older Word documents 
import tempfile 
import uuid 
import zipfile
from collections import Counter
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

from docx import Document
from flask import Flask, render_template, jsonify, request, send_file
from pypdf import PdfReader
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # Limited total resume import to ~100mb 
app.config["MAX_FORM_MEMORY_SIZE"] = 4 * 1024 * 1024  # Limiting JD import to ~4mb 

SUPPORTED_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".txt", ".rtf",
    ".odt", ".html", ".htm", ".md"
}

STOP_WORDS = set("""a an and are as at be been being by can did do does for from had has have he her hers 
him his i if in into is it its job of on or our she that the their them they this to was we were will with 
you your about across after all also am any apply applicant applicants appropriate able ability based best both business 
candidate candidates company demonstrate duties experience experienced expert familiar first following good great high including 
knowledge looking minimum must new not one other people position preferred requirements required role skills strong suitable team 
work worked writing years""".split())
# Exports here is to create an in-memory dictionary that we later save with a uuid and file_name path for download 
EXPORTS: dict[str, Path] = {}

class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.hidden_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "head"}:
            self.hidden_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "head"} and self.hidden_depth:
            self.hidden_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.hidden_depth:
            self.parts.append(data)


def decode_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def extract_resume_text(filename: str, data: bytes) -> str:
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError("Unsupported file type")

    if extension == ".pdf":
        reader = PdfReader(io.BytesIO(data), strict=False)
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    if extension == ".docx":
        document = Document(io.BytesIO(data))
        parts = [paragraph.text for paragraph in document.paragraphs]
        for table in document.tables:
            for row in table.rows:
                parts.append(" ".join(cell.text for cell in row.cells))
        return "\n".join(parts)

    if extension == ".doc":
        antiword = shutil.which("antiword")
        if not antiword:
            raise ValueError("Legacy .doc extraction needs antiword installed on the computer running Flask")
        with tempfile.NamedTemporaryFile(suffix=".doc") as temporary:
            temporary.write(data)
            temporary.flush()
            result = subprocess.run(
                [antiword, temporary.name], capture_output=True, timeout=20, check=False
            )
        if result.returncode != 0:
            raise ValueError("Could not read this .doc file")
        return decode_text(result.stdout)

    if extension == ".odt":
        from xml.etree import ElementTree

        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            xml_data = archive.read("content.xml")
        root = ElementTree.fromstring(xml_data)
        return " ".join(text for text in root.itertext() if text.strip())

    text = decode_text(data)
    if extension in {".html", ".htm"}:
        parser = TextExtractor()
        parser.feed(text)
        return " ".join(parser.parts)
    if extension == ".rtf":
        text = re.sub(r"\\'[0-9a-fA-F]{2}", " ", text)
        text = re.sub(r"\\[a-zA-Z]+-?\d* ?", " ", text)
        text = re.sub(r"\\[^a-zA-Z]", " ", text)
        return re.sub(r"[{}]", " ", text)
    return text


def tokenize(text: str) -> list[str]:
    return [
        token.lower()
        for token in re.findall(r"[\w+#.-]+", text, flags=re.UNICODE)
        if len(token) > 2 and token.lower() not in STOP_WORDS and not token.isdigit()
    ]

# Applying dot product between the 2 vectors and their Norms, to get TF-IDF cosine values 
def cosine_similarity(left: dict[str, float], right: dict[str, float]) -> float:
    dot = sum(value * right.get(term, 0.0) for term, value in left.items())
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def rank_resumes(job_description: str, resumes: list[dict[str, object]]) -> list[dict[str, object]]:
    jd_tokens = tokenize(job_description)
    if not jd_tokens:
        raise ValueError("The job description needs more searchable text to rank resumes.")

    resume_tokens = [tokenize(str(resume["text"])) for resume in resumes]
    documents = [jd_tokens, *resume_tokens]
    document_frequency: Counter[str] = Counter()
    for tokens in documents:
        document_frequency.update(set(tokens))

    document_count = len(documents)
    idf = {
        term: math.log((document_count + 1) / (frequency + 1)) + 1
        for term, frequency in document_frequency.items()
    }

    def vectorize(tokens: list[str]) -> dict[str, float]:
        counts = Counter(tokens)
        return {
            term: (1 + math.log(count)) * idf.get(term, 1.0)
            for term, count in counts.items()
            if count > 0
        }

    jd_vector = vectorize(jd_tokens)
    jd_terms = set(jd_tokens)
    ranked: list[dict[str, object]] = []
    for resume, tokens in zip(resumes, resume_tokens):
        candidate_vector = vectorize(tokens)
        similarity = cosine_similarity(jd_vector, candidate_vector)
        present = jd_terms.intersection(tokens)
        coverage = len(present) / max(1, len(jd_terms))
        score = 100 * (0.7 * similarity + 0.3 * coverage)
        ranked.append({
            "filename": str(resume["filename"]),
            "data": resume["data"],
            "score": round(score, 1),
            "matched_terms": sorted(present)[:8],
            "missing_terms": sorted(jd_terms - present)[:8],
        })

    ranked.sort(key=lambda item: (-float(item["score"]), str(item["filename"]).casefold()))
    return ranked


def output_root() -> Path:
    configured = os.environ.get("RESUME_RANKER_OUTPUT_DIR")
    return Path(configured).expanduser() if configured else Path.home() / "Desktop"


# Basic Home page "/"
@app.get("/")
def index():
    return render_template("index.html")

# Ranking page 
@app.post("/rank")
def rank():
    job_description = request.form.get("job_description", "").strip()
    files = request.files.getlist("resumes")
    if not job_description:
        return jsonify(error="Paste the job description before ranking."), 400
    if not files or not any(file.filename for file in files):
        return jsonify(error="Choose a folder containing resumes before ranking."), 400

    resumes: list[dict[str, object]] = []
    skipped: list[dict[str, str]] = []
    for uploaded in files:
        original_name = uploaded.filename or ""
        if not original_name:
            continue
        filename = Path(original_name.replace("\\", "/")).name
        if filename.startswith("."):
            continue
        if Path(filename).suffix.lower() not in SUPPORTED_EXTENSIONS:
            skipped.append({"filename": filename, "reason": "Unsupported file type"})
            continue
        data = uploaded.read()
        try:
            text = extract_resume_text(filename, data)
            if len(tokenize(text)) < 3:
                raise ValueError("No readable resume text found (the file may be scanned or empty)")
            resumes.append({"filename": filename, "data": data, "text": text})
        except Exception as error:
            skipped.append({"filename": filename, "reason": str(error)[:180]})

    if not resumes:
        details = "; ".join(f"{item['filename']}: {item['reason']}" for item in skipped[:3])
        message = "No readable resumes were found. Use text-based PDFs or supported document files."
        if details:
            message += " " + details
        return jsonify(error=message), 400

    try:
        ranked = rank_resumes(job_description, resumes)
    except ValueError as error:
        return jsonify(error=str(error)), 400

    job_id = uuid.uuid4().hex[:10]
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    desktop = output_root()
    desktop.mkdir(parents=True, exist_ok=True)
    export_dir = desktop / f"Ranked_Resumes_{timestamp}_{job_id}"
    export_dir.mkdir(parents=False, exist_ok=False)

    result_items = []
    for index, resume in enumerate(ranked, start=1):
        safe_name = secure_filename(str(resume["filename"])) or f"resume_{index}"
        output_name = f"{index:02d} - {float(resume['score']):.1f}% - {safe_name}"
        (export_dir / output_name).write_bytes(resume["data"])
        result_items.append({
            "rank": index,
            "filename": str(resume["filename"]),
            "score": resume["score"],
            "matched_terms": resume["matched_terms"],
            "missing_terms": resume["missing_terms"],
        })

    zip_path = desktop / f"{export_dir.name}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(export_dir.iterdir()):
            if path.is_file():
                archive.write(path, arcname=path.name)
    EXPORTS[job_id] = zip_path

    return jsonify(
        items=result_items,
        skipped=skipped,
        output_folder=str(export_dir),
        download_url=f"/download/{job_id}",
        note="Scores reflect text overlap with the job description only; review each resume yourself. This is not a hiring decision.",
    )


# Get endpoint by unique resume_id number then error handle if null/none, return as an attachment + zip file 
@app.get("/download/<job_id>")
def download(job_id: str):
    zip_path = EXPORTS.get(job_id)
    if not zip_path or not zip_path.is_file():
        return "This export is not longer availalbe, Run the ranking again.", 404 
    return send_file(zip_path, as_attachment=True, download_name="ranked_resume.zip", mimetype="application/zip")



if __name__ == "__main__":
    app.run(host= "127.0.0.1", debug=True)