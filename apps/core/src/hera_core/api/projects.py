"""Projects: a container with behaviour, not a folder."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status

from hera_chats import Project, ProjectRepository
from hera_core.deps import Db, Owner, not_found
from hera_core.schemas import ProjectIn, ProjectOut, ProjectPatch

router = APIRouter(tags=["projects"])


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(owner: Owner, db: Db, include_archived: bool = False) -> list[ProjectOut]:
    projects = ProjectRepository(db).for_owner(owner, include_archived=include_archived)
    return [ProjectOut.of(project) for project in projects]


@router.post("/projects", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectIn, owner: Owner, db: Db) -> ProjectOut:
    project = ProjectRepository(db).create(
        owner,
        payload.name,
        instructions=payload.instructions,
        pinned_skills=list(payload.pinned_skills),
        default_profile_id=payload.default_profile_id,
    )
    return ProjectOut.of(project)


@router.get("/projects/{project_id}", response_model=ProjectOut)
def read_project(project_id: UUID, owner: Owner, db: Db) -> ProjectOut:
    return ProjectOut.of(_require(db, project_id, owner))


@router.patch("/projects/{project_id}", response_model=ProjectOut)
def update_project(project_id: UUID, payload: ProjectPatch, owner: Owner, db: Db) -> ProjectOut:
    """Patch, not put: the settings screen edits one field at a time, and a full replace would
    make a stale tab overwrite everything else on the way past."""
    projects = ProjectRepository(db)
    project = _require(db, project_id, owner)

    if payload.name is not None:
        project.name = payload.name
    if payload.instructions is not None:
        project.instructions = payload.instructions
    if payload.default_profile_id is not None:
        project.default_profile_id = payload.default_profile_id
    if payload.archived is not None:
        project.archived = payload.archived
    if payload.pinned_skills is not None:
        project.pinned_skills = list(payload.pinned_skills)

    return ProjectOut.of(projects.save(project))


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: UUID, owner: Owner, db: Db) -> None:
    """Revoke, not delete.

    The chats inside keep their ``project_id`` and are simply no longer reachable through a
    project that is gone. A hard delete would leave those rows pointing at nothing, and the
    reference is a bare UUID with no foreign key to complain.
    """
    ProjectRepository(db).revoke(_require(db, project_id, owner).id)


def _require(db: Db, project_id: UUID, owner: UUID) -> Project:
    project = ProjectRepository(db).get(project_id)
    if project is None or project.owner_id != owner:
        raise not_found("project")
    return project
