"""Role management endpoints for RBAC."""

import uuid
from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db, CurrentSuperuser
from src.api.v1.schemas.auth import RoleCreate, RoleResponse, UserRoleUpdate
from src.db.models.user import Role, User, user_roles
from src.db.repositories.user import UserRepository

import structlog

logger = structlog.get_logger()

router = APIRouter()


class RoleRepository:
    """Repository for Role model operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: dict) -> Role:
        """Create a new role."""
        role = Role(**data)
        self.session.add(role)
        await self.session.flush()
        return role

    async def get_by_id(self, role_id: uuid.UUID) -> Role | None:
        """Get a role by ID."""
        stmt = select(Role).where(Role.id == role_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Role | None:
        """Get a role by name."""
        stmt = select(Role).where(Role.name == name)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(self) -> List[Role]:
        """Get all roles."""
        stmt = select(Role).order_by(Role.name)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update(self, role_id: uuid.UUID, data: dict) -> Role | None:
        """Update a role."""
        role = await self.get_by_id(role_id)
        if role:
            for key, value in data.items():
                setattr(role, key, value)
            await self.session.flush()
        return role

    async def delete(self, role_id: uuid.UUID) -> bool:
        """Delete a role."""
        role = await self.get_by_id(role_id)
        if role:
            await self.session.delete(role)
            await self.session.flush()
            return True
        return False


@router.post("", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    role_data: RoleCreate,
    current_user: CurrentSuperuser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RoleResponse:
    """Create a new role (superuser only)."""
    role_repo = RoleRepository(db)
    
    existing = await role_repo.get_by_name(role_data.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role with this name already exists",
        )
    
    role = await role_repo.create({
        "name": role_data.name,
        "description": role_data.description,
        "permissions": role_data.permissions,
    })
    await db.commit()
    
    logger.info(
        "Role created",
        role_id=str(role.id),
        role_name=role.name,
        by_user=str(current_user.id),
    )
    
    return RoleResponse.model_validate(role)


@router.get("", response_model=List[RoleResponse])
async def list_roles(
    current_user: CurrentSuperuser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> List[RoleResponse]:
    """List all roles (superuser only)."""
    role_repo = RoleRepository(db)
    roles = await role_repo.get_all()
    return [RoleResponse.model_validate(r) for r in roles]


@router.get("/{role_id}", response_model=RoleResponse)
async def get_role(
    role_id: uuid.UUID,
    current_user: CurrentSuperuser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RoleResponse:
    """Get a specific role (superuser only)."""
    role_repo = RoleRepository(db)
    role = await role_repo.get_by_id(role_id)
    
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )
    
    return RoleResponse.model_validate(role)


@router.patch("/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: uuid.UUID,
    role_data: RoleCreate,
    current_user: CurrentSuperuser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RoleResponse:
    """Update a role (superuser only)."""
    role_repo = RoleRepository(db)
    role = await role_repo.get_by_id(role_id)
    
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )
    
    if role_data.name != role.name:
        existing = await role_repo.get_by_name(role_data.name)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Role with this name already exists",
            )
    
    updated_role = await role_repo.update(role_id, {
        "name": role_data.name,
        "description": role_data.description,
        "permissions": role_data.permissions,
    })
    await db.commit()
    
    logger.info(
        "Role updated",
        role_id=str(role_id),
        by_user=str(current_user.id),
    )
    
    return RoleResponse.model_validate(updated_role)


@router.delete("/{role_id}")
async def delete_role(
    role_id: uuid.UUID,
    current_user: CurrentSuperuser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Delete a role (superuser only)."""
    role_repo = RoleRepository(db)
    role = await role_repo.get_by_id(role_id)
    
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )
    
    await role_repo.delete(role_id)
    await db.commit()
    
    logger.info(
        "Role deleted",
        role_id=str(role_id),
        by_user=str(current_user.id),
    )
    
    return {"message": "Role deleted successfully"}


@router.post("/users/{user_id}/roles", response_model=dict)
async def assign_roles_to_user(
    user_id: uuid.UUID,
    role_data: UserRoleUpdate,
    current_user: CurrentSuperuser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Assign roles to a user (superuser only)."""
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(str(user_id))
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    role_repo = RoleRepository(db)
    roles = []
    
    for rid in role_data.role_ids:
        role = await role_repo.get_by_id(rid)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Role {rid} not found",
            )
        roles.append(role)
    
    user.roles = roles
    await db.commit()
    
    logger.info(
        "Roles assigned to user",
        user_id=str(user_id),
        role_ids=[str(r.id) for r in roles],
        by_user=str(current_user.id),
    )
    
    return {"message": f"Assigned {len(roles)} role(s) to user"}


@router.get("/users/{user_id}/roles", response_model=List[RoleResponse])
async def get_user_roles(
    user_id: uuid.UUID,
    current_user: CurrentSuperuser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> List[RoleResponse]:
    """Get roles for a user (superuser only)."""
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(str(user_id))
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    return [RoleResponse.model_validate(r) for r in user.roles]


PREDEFINED_PERMISSIONS = [
    "documents:read",
    "documents:write",
    "documents:delete",
    "queries:read",
    "queries:write",
    "agents:read",
    "agents:execute",
    "admin:users",
    "admin:roles",
    "admin:settings",
]


@router.get("/permissions/list", response_model=List[str])
async def list_available_permissions(
    current_user: CurrentSuperuser,
) -> List[str]:
    """List all available permissions (superuser only)."""
    return PREDEFINED_PERMISSIONS
