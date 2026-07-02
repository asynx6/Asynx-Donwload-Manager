"""
AsynxDL — Settings Routes
~~~~~~~~~~~~~~~~~~~~~~~~~
GET & PUT /settings dengan autentikasi.
"""

from fastapi import APIRouter, Depends

from backend.api.auth import verify_token
from backend.api.models import SettingsModel
from backend.api.state import manager
from backend.system.config import load_config, save_config
from backend.system.startup import set_startup

router = APIRouter(dependencies=[Depends(verify_token)])


@router.get("", response_model=SettingsModel)
async def get_settings():
    config = load_config()
    # Mask token untuk keamanan: jangan expose full secret di UI
    return SettingsModel(**config)


@router.put("")
async def put_settings(settings: SettingsModel):
    config = load_config()
    update = settings.model_dump(exclude_unset=True)
    # Jangan overwrite secret token dengan string kosong dari UI
    if "api_secret_token" in update and not update["api_secret_token"]:
        del update["api_secret_token"]
    config.update(update)
    save_config(config)

    # Apply runtime settings
    if "max_concurrent_downloads" in update:
        manager.set_max_concurrent(update["max_concurrent_downloads"])

    # Apply startup registry
    if "run_on_startup" in update:
        set_startup(update["run_on_startup"])

    return SettingsModel(**config)
