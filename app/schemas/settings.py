from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ThemeMode = Literal["light", "dark", "system"]
Language = Literal["English"]


class SettingsRead(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    language: Language
    theme_mode: ThemeMode = Field(validation_alias="themeMode", serialization_alias="themeMode")
    notifications_enabled: bool = Field(validation_alias="notificationsEnabled", serialization_alias="notificationsEnabled")


class PreferencesUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    language: Language | None = None
    theme_mode: ThemeMode | None = Field(default=None, validation_alias="themeMode", serialization_alias="themeMode")
    notifications_enabled: bool | None = Field(default=None, validation_alias="notificationsEnabled", serialization_alias="notificationsEnabled")


class SettingsUpdateResponse(BaseModel):
    message: str
    settings: SettingsRead
