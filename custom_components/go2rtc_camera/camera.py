from homeassistant.components.camera import (
    Camera,
    CameraEntityCapabilities,
    CameraEntityFeature,
    CameraWebRTCProvider,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DOMAIN
from .provider import XProvider


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    if server := entry.options.get("server"):
        assert isinstance(server, str)
        source = entry.options.get("url")
        assert isinstance(source, str)

        provider = XProvider(hass, server, source)
        async_add_entities([ExternalCamera(entry, provider)])
    else:
        async_add_entities([InternalCamera(entry)])


class InternalCamera(Camera):
    _stream_source: str

    def __init__(self, config: ConfigEntry):
        super().__init__()

        self._attr_unique_id = config.entry_id
        self._attr_name = config.title
        self._attr_camera_entity_capabilities = CameraEntityCapabilities(
            two_way_audio=config.options.get("two_way") is True
        )
        self._attr_supported_features = CameraEntityFeature.STREAM

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config.entry_id)},
        )

        self._stream_source = config.options["url"]

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        assert self._webrtc_provider
        return await self._webrtc_provider.async_get_image(self, width, height)

    async def stream_source(self) -> str | None:
        return self._stream_source


class ExternalCamera(InternalCamera):
    def __init__(self, config: ConfigEntry, provider: CameraWebRTCProvider):
        super().__init__(config)

        self._stream_source = None
        self._supports_native_async_webrtc = True
        self._webrtc_provider = provider

    async def async_refresh_providers(self, *, write_state: bool = True) -> None:
        pass  # fix self._webrtc_provider = None

    async def stream_source(self) -> str | None:
        if not self._stream_source and isinstance(self._webrtc_provider, XProvider):
            self._stream_source = await self._webrtc_provider.rtsp_url()

        return self._stream_source
