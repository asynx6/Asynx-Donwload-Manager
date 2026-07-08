"""
AsynxDL — Settings Routes
~~~~~~~~~~~~~~~~~~~~~~~~~
GET & PUT /settings.
"""

from fastapi import APIRouter

from backend.api.models import SettingsModel
from backend.api.state import manager
from backend.system.config import load_config, save_config
from backend.system.startup import set_startup

router = APIRouter()


@router.get("", response_model=SettingsModel)
async def get_settings():
    config = load_config()
    return SettingsModel(**config)


@router.put("")
async def put_settings(settings: SettingsModel):
    config = load_config()
    update = settings.model_dump(exclude_unset=True)
    config.update(update)
    save_config(config)

    # Apply runtime settings
    if "max_concurrent_downloads" in update:
        manager.set_max_concurrent(update["max_concurrent_downloads"])

    if "speed_limit_kbps" in update:
        manager.update_global_speed_limit(update["speed_limit_kbps"])

    # Apply startup registry
    if "run_on_startup" in update:
        set_startup(update["run_on_startup"])

    return SettingsModel(**config)
