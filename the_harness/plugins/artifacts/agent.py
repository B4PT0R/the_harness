"""Typed, bounded data presentations; never executable widgets."""

import json
from typing import Literal

from modict import modict
from the_framework.agent import Artifact, tool
from the_framework.plugins.artifacts.agent import ArtifactsExtension


class Payload(modict):
    _config = modict.config(extra="forbid", strict=True, allow_inf_nan=False)
    title: str = ""
    description: str = ""

    @modict.model_validator(mode="after")
    def bounded(self):
        if len(json.dumps(self, ensure_ascii=False, allow_nan=False).encode()) > 300_000:
            raise ValueError("artifact payload exceeds 300 KB; publish a file instead")
        if len(self.title) > 300 or len(self.description) > 2000:
            raise ValueError("title/description exceed 300/2000 characters")


class MarkdownPayload(Payload):
    content: str

    @modict.validator("content", mode="after")
    def bounded_content(self, value):
        if len(value) > 100_000:
            raise ValueError("content exceeds 100000 characters; publish a file instead")
        return value


class CodePayload(MarkdownPayload):
    language: str = "text"
    filename: str = "snippet.txt"

    @modict.model_validator(mode="after")
    def bounded_labels(self):
        if len(self.language) > 40 or len(self.filename) > 200:
            raise ValueError("language/filename exceed 40/200 characters")


Cell = str | int | float | bool | None


class TablePayload(Payload):
    columns: list[str]
    rows: list[list[Cell]]

    @modict.model_validator(mode="after")
    def rectangular(self):
        if not 1 <= len(self.columns) <= 30 or len(set(self.columns)) != len(self.columns):
            raise ValueError("table needs 1–30 unique column labels")
        if any(not column.strip() or len(column) > 200 for column in self.columns):
            raise ValueError("column labels must be nonempty and at most 200 characters")
        if len(self.rows) > 2000 or any(len(row) != len(self.columns) for row in self.rows):
            raise ValueError("table needs at most 2000 rectangular rows")


class Series(modict):
    _config = Payload._config
    name: str
    values: list[int | float]


class ChartPayload(Payload):
    chart_type: Literal["bar", "line"] = "bar"
    labels: list[str]
    series: list[Series]
    unit: str = ""

    @modict.validator("series", mode="before")
    def parse_series(self, value):
        if not isinstance(value, list):
            raise TypeError("series must be a list")
        return [Series(item) for item in value]

    @modict.model_validator(mode="after")
    def aligned(self):
        if not 1 <= len(self.labels) <= 200 or not 1 <= len(self.series) <= 6:
            raise ValueError("chart needs 1–200 labels and 1–6 series")
        if any(len(series["values"]) != len(self.labels) for series in self.series):
            raise ValueError("each series must have one finite value per label")
        if any(len(label) > 200 for label in self.labels) or len(self.unit) > 40:
            raise ValueError("labels/unit exceed 200/40 characters")
        if any(not series.name.strip() or len(series.name) > 200 for series in self.series):
            raise ValueError("series names must be nonempty and at most 200 characters")


class TimelineEntry(modict):
    _config = Payload._config
    label: str
    title: str
    detail: str = ""


class TimelinePayload(Payload):
    entries: list[TimelineEntry]

    @modict.validator("entries", mode="before")
    def parse_entries(self, value):
        if not isinstance(value, list):
            raise TypeError("entries must be a list")
        return [TimelineEntry(item) for item in value]

    @modict.model_validator(mode="after")
    def bounded_entries(self):
        if not 1 <= len(self.entries) <= 100:
            raise ValueError("timeline needs 1–100 entries, in display order")
        if any(len(entry.label) > 100 or len(entry.title) > 300 or len(entry.detail) > 2000
               for entry in self.entries):
            raise ValueError("timeline label/title/detail exceed 100/300/2000 characters")


class MarkdownArtifact(Artifact):
    """A standalone Markdown document, with safe math rendering and text export (100000 characters max)."""
    kind = "markdown"
    payload: MarkdownPayload = modict.field(required="always")
    payload_example = modict.attr({"title": "Note", "content": "## Résumé\n\nUn document **autonome**."})


class CodeArtifact(Artifact):
    """Literal code/text with copy and download, never execution (100000 characters max)."""
    kind = "code"
    payload: CodePayload = modict.field(required="always")
    payload_example = modict.attr({"title": "Exemple Python", "language": "python", "filename": "hello.py", "content": "print('Bonjour')\n"})


class TableArtifact(Artifact):
    """Filterable, sortable table with CSV export. 1–30 unique columns, up to 2000 rectangular rows of scalar cells."""
    kind = "table"
    payload: TablePayload = modict.field(required="always")
    payload_example = modict.attr({"title": "Comparaison", "columns": ["Option", "Coût"], "rows": [["A", 12], ["B", 18]]})


class ChartArtifact(Artifact):
    """Bar/line chart with accessible data table and CSV. 1–200 labels, 1–6 series; finite values aligned to labels. Equally spaced categorical x-axis, not a continuous time axis."""
    kind = "chart"
    payload: ChartPayload = modict.field(required="always")
    payload_example = modict.attr({"title": "Évolution", "chart_type": "line", "labels": ["Jan", "Fév", "Mar"], "series": [{"name": "Volume", "values": [12, 18, 15]}], "unit": "unités"})


class TimelineArtifact(Artifact):
    """Read-only chronology or plan; 1–100 entries in supplied order. Labels are literal, no timezone inference, reminders or task completion."""
    kind = "timeline"
    payload: TimelinePayload = modict.field(required="always")
    payload_example = modict.attr({"title": "Étapes", "entries": [{"label": "Étape 1", "title": "Préparer", "detail": "Rassembler les éléments."}, {"label": "Étape 2", "title": "Vérifier"}]})


class HarnessArtifacts(ArtifactsExtension):
    artifact_types = (MarkdownArtifact, CodeArtifact, TableArtifact, ChartArtifact, TimelineArtifact)
    instructions = ArtifactsExtension.instructions + (
        " The Harness additionally supports markdown, code, table, chart and timeline. "
        "Consult supported_artifacts for their exact schemas. Use artifacts for reusable "
        "deliverables or data exploration, not to wrap every reply. All custom payloads "
        "are limited to 300 KB, titles to 300 and descriptions to 2000 characters. "
        "Code is never executed. Timeline is read-only and never schedules anything. "
        "For larger data, publish a file with a concise preview."
    )

    @tool
    async def show_artifact(self, kind: str, payload: dict):
        """
        description: Present a durable artifact. Use supported_artifacts for exact payload schemas and examples.
        strict: false
        """
        return await super().show_artifact(kind, payload)
