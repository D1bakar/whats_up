from app.api.v1.auth import router as auth_router
from app.api.v1.contacts import router as contacts_router
from app.api.v1.conversations import router as conversations_router
from app.api.v1.me import router as me_router
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1")
router.include_router(auth_router)
router.include_router(me_router)
router.include_router(conversations_router)
router.include_router(contacts_router)
