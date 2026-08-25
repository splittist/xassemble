from __future__ import annotations

import os
import re
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .auth import (
    DEFAULT_SESSION_SECONDS,
    SESSION_COOKIE,
    SessionManager,
    authenticate,
    public_user,
)
from .database import Database, load_schema
from .parser import QuestionnaireError, parse_questionnaire
from .service import (
    GenerationError,
    generate_documents,
    questionnaire_visibility,
    validate_questionnaire_against_templates,
)
from .validation import TemplateError, validate_template

DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LABEL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
PUBLIC_PATHS = {"/health", "/auth/login"}
PROTECTED_PREFIXES = ("/auth", "/document-sets", "/docs", "/openapi.json")


class DocumentSetCreate(BaseModel):
    slug: str
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=1000)


class AnswersRequest(BaseModel):
    answers: dict[str, object] = Field(default_factory=dict)


class GenerateRequest(AnswersRequest):
    project_code: str = Field(min_length=1, max_length=100)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)


def create_app(
    database_path: str | Path | None = None,
    secret_key: str | None = None,
    secure_cookies: bool | None = None,
    session_seconds: int | None = None,
    frontend_dist: str | Path | None = None,
) -> FastAPI:
    path = database_path or os.environ.get("XASSEMBLE_DB", "data/xassemble.sqlite3")
    database = Database(path)
    configured_secret = secret_key or os.environ.get("XASSEMBLE_SECRET_KEY")
    cookie_secure = (
        secure_cookies
        if secure_cookies is not None
        else os.environ.get("XASSEMBLE_SECURE_COOKIES", "false").lower() == "true"
    )
    session_lifetime = session_seconds or int(
        os.environ.get("XASSEMBLE_SESSION_SECONDS", DEFAULT_SESSION_SECONDS)
    )
    frontend_path = Path(
        frontend_dist
        or os.environ.get("XASSEMBLE_FRONTEND_DIST", "")
        or Path(__file__).resolve().parents[2] / "frontend" / "dist"
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        if not configured_secret:
            raise RuntimeError("XASSEMBLE_SECRET_KEY is required")
        database.initialize()
        application.state.sessions = SessionManager(configured_secret, session_lifetime)
        yield

    app = FastAPI(title="xassemble", version="0.1.0", lifespan=lifespan)
    app.state.database = database

    @app.middleware("http")
    async def require_active_user(request: Request, call_next):
        requires_auth = request.url.path.startswith(PROTECTED_PREFIXES)
        if request.url.path in PUBLIC_PATHS or not requires_auth:
            return await call_next(request)
        token = request.cookies.get(SESSION_COOKIE)
        sessions: SessionManager = request.app.state.sessions
        user_id = sessions.read(token) if token else None
        user = database.get_user(user_id) if user_id is not None else None
        if user is None or not user["active"]:
            return JSONResponse(
                {"detail": "Authentication required"},
                status_code=401,
                headers={"WWW-Authenticate": "Session"},
            )
        request.state.user = user
        return await call_next(request)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/auth/login")
    def login(payload: LoginRequest, response: Response) -> dict[str, object]:
        try:
            user = authenticate(database, payload.username, payload.password)
        except ValueError:
            user = None
        if user is None:
            raise HTTPException(401, "Invalid username or password")
        response.set_cookie(
            SESSION_COOKIE,
            app.state.sessions.create(user["id"]),
            max_age=session_lifetime,
            httponly=True,
            secure=cookie_secure,
            samesite="lax",
            path="/",
        )
        return public_user(user)

    @app.post("/auth/logout", status_code=204)
    def logout(response: Response) -> None:
        response.delete_cookie(SESSION_COOKIE, path="/", secure=cookie_secure, samesite="lax")

    @app.get("/auth/me")
    def me(request: Request) -> dict[str, object]:
        return public_user(request.state.user)

    @app.get("/document-sets")
    def list_document_sets() -> list[dict[str, object]]:
        return database.list_document_sets()

    @app.post("/document-sets", status_code=201)
    def create_document_set(payload: DocumentSetCreate) -> dict[str, object]:
        if not SLUG.fullmatch(payload.slug):
            raise HTTPException(422, "slug must contain lowercase letters, digits, and single hyphens")
        try:
            return database.create_document_set(payload.slug, payload.name, payload.description)
        except sqlite3.IntegrityError as exc:
            raise HTTPException(409, "A document set with that slug already exists") from exc

    @app.post("/document-sets/{slug}/questionnaire-versions", status_code=201)
    async def upload_questionnaire(
        slug: str,
        request: Request,
        file: Annotated[UploadFile, File()],
        note: Annotated[str, Form(max_length=1000)] = "",
    ) -> dict[str, object]:
        document_set = _document_set(database, slug)
        content = await _docx_upload(file)
        try:
            schema = parse_questionnaire(content)
            validate_questionnaire_against_templates(
                schema, database.current_templates(document_set["id"])
            )
        except (QuestionnaireError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from exc

        current = database.get_questionnaire(document_set["id"])
        old_variables = load_schema(current).variables if current else set()
        row = database.add_questionnaire(
            document_set["id"], content, schema, request.state.user["username"], note.strip()
        )
        return {
            "id": row["id"],
            "version_no": row["version_no"],
            "is_current": False,
            "summary": {
                "questions": len(schema.questions),
                "outputs": len(schema.outputs),
                "variables_added": sorted(schema.variables - old_variables),
                "variables_removed": sorted(old_variables - schema.variables),
            },
        }

    @app.post("/document-sets/{slug}/template-versions", status_code=201)
    async def upload_template(
        slug: str,
        request: Request,
        label: Annotated[str, Form()],
        file: Annotated[UploadFile, File()],
        note: Annotated[str, Form(max_length=1000)] = "",
    ) -> dict[str, object]:
        document_set = _document_set(database, slug)
        if not LABEL.fullmatch(label):
            raise HTTPException(422, "label must be a valid identifier")
        questionnaire = database.get_questionnaire(document_set["id"])
        if questionnaire is None:
            raise HTTPException(409, "Publish a questionnaire before uploading templates")
        content = await _docx_upload(file)
        try:
            variables = validate_template(content, load_schema(questionnaire))
        except TemplateError as exc:
            raise HTTPException(422, str(exc)) from exc
        row = database.add_template(
            document_set["id"],
            label,
            content,
            request.state.user["username"],
            note.strip(),
        )
        return {
            "id": row["id"],
            "label": label,
            "version_no": row["version_no"],
            "is_current": False,
            "template_variables": sorted(variables),
        }

    @app.post("/document-sets/{slug}/questionnaire-versions/{version_id}/publish")
    def publish_questionnaire(slug: str, version_id: int) -> dict[str, object]:
        document_set = _document_set(database, slug)
        candidate = database.get_questionnaire(document_set["id"], version_id)
        if candidate is None:
            raise HTTPException(404, "Questionnaire version not found")
        try:
            validate_questionnaire_against_templates(
                load_schema(candidate), database.current_templates(document_set["id"])
            )
            database.publish_questionnaire(document_set["id"], version_id)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {"id": version_id, "is_current": True}

    @app.post("/document-sets/{slug}/template-versions/{version_id}/publish")
    def publish_template(slug: str, version_id: int) -> dict[str, object]:
        document_set = _document_set(database, slug)
        candidate = database.get_template(document_set["id"], version_id=version_id)
        if candidate is None:
            raise HTTPException(404, "Template version not found")
        questionnaire = database.get_questionnaire(document_set["id"])
        if questionnaire is None:
            raise HTTPException(409, "No questionnaire is published")
        try:
            validate_template(candidate["docx_blob"], load_schema(questionnaire))
            database.publish_template(document_set["id"], version_id)
        except TemplateError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {"id": version_id, "label": candidate["label"], "is_current": True}

    @app.get("/document-sets/{slug}/versions")
    def versions(slug: str) -> dict[str, object]:
        document_set = _document_set(database, slug)
        return database.list_versions(document_set["id"])

    @app.get("/document-sets/{slug}/questionnaire")
    def questionnaire(slug: str) -> dict[str, object]:
        _, row = _current_questionnaire(database, slug)
        schema = load_schema(row)
        return {
            "version_id": row["id"],
            "questions": [question.to_dict() for question in schema.questions],
        }

    @app.post("/document-sets/{slug}/questionnaire/evaluate")
    def evaluate(slug: str, payload: AnswersRequest) -> dict[str, list[str]]:
        _, row = _current_questionnaire(database, slug)
        visible, hidden, _ = questionnaire_visibility(load_schema(row), payload.answers)
        return {"visible": visible, "hidden": hidden}

    @app.post("/document-sets/{slug}/generate")
    def generate(slug: str, payload: GenerateRequest, request: Request) -> Response:
        document_set, questionnaire_row = _current_questionnaire(database, slug)
        try:
            content, filename, media_type = generate_documents(
                database,
                document_set["id"],
                questionnaire_row,
                payload.answers,
                payload.project_code,
                request.state.user["username"],
            )
        except (GenerationError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from exc
        return _download(content, filename, media_type)

    @app.get("/document-sets/{slug}/current/questionnaire")
    def download_current_questionnaire(slug: str) -> Response:
        _, row = _current_questionnaire(database, slug)
        return _download(row["docx_blob"], f"questionnaire-v{row['version_no']}.docx")

    @app.get("/document-sets/{slug}/current/templates/{label}")
    def download_current_template(slug: str, label: str) -> Response:
        document_set = _document_set(database, slug)
        row = database.get_template(document_set["id"], label=label)
        if row is None:
            raise HTTPException(404, "Published template not found")
        return _download(row["docx_blob"], f"{label}-v{row['version_no']}.docx")

    @app.get("/document-sets/{slug}/versions/{kind}/{version_id}")
    def download_version(
        slug: str, kind: Literal["questionnaire", "template"], version_id: int
    ) -> Response:
        document_set = _document_set(database, slug)
        if kind == "questionnaire":
            row = database.get_questionnaire(document_set["id"], version_id)
            filename = f"questionnaire-v{row['version_no']}.docx" if row else ""
        else:
            row = database.get_template(document_set["id"], version_id=version_id)
            filename = f"{row['label']}-v{row['version_no']}.docx" if row else ""
        if row is None:
            raise HTTPException(404, "Version not found")
        return _download(row["docx_blob"], filename)

    if frontend_path.joinpath("index.html").is_file():
        assets_path = frontend_path / "assets"
        if assets_path.is_dir():
            app.mount("/assets", StaticFiles(directory=assets_path), name="frontend-assets")

        @app.get("/", include_in_schema=False)
        @app.get("/sets/{frontend_route:path}", include_in_schema=False)
        def frontend(frontend_route: str = "") -> FileResponse:
            return FileResponse(frontend_path / "index.html")

    return app


def _document_set(database: Database, slug: str) -> dict[str, object]:
    row = database.get_document_set(slug)
    if row is None:
        raise HTTPException(404, "Document set not found")
    return row


def _current_questionnaire(
    database: Database, slug: str
) -> tuple[dict[str, object], dict[str, object]]:
    document_set = _document_set(database, slug)
    row = database.get_questionnaire(document_set["id"])
    if row is None:
        raise HTTPException(404, "No questionnaire is published")
    return document_set, row


async def _docx_upload(file: UploadFile) -> bytes:
    if not file.filename or not file.filename.lower().endswith(".docx"):
        raise HTTPException(422, "Upload must be a .docx file")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if not content:
        raise HTTPException(422, "Upload is empty")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Upload exceeds the 10 MB limit")
    return content


def _download(content: bytes, filename: str, media_type: str = DOCX_MEDIA_TYPE) -> Response:
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


app = create_app()
