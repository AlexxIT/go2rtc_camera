import hashlib
import logging
import re

from go2rtc_client import Go2RtcRestClient
from go2rtc_client.ws import (
    Go2RtcWsClient,
    ReceiveMessages,
    WebRTCAnswer,
    WebRTCCandidate,
    WebRTCOffer,
    WsError,
)
from homeassistant.components.camera import (
    Camera,
    CameraWebRTCProvider,
    WebRTCAnswer as HAWebRTCAnswer,
    WebRTCCandidate as HAWebRTCCandidate,
    WebRTCError,
    WebRTCMessage,
    WebRTCSendMessage,
)
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from webrtc_models import RTCIceCandidateInit

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


class XProvider(CameraWebRTCProvider):
    _sessions: dict[str, Go2RtcWsClient] = {}

    def __init__(self, hass, server: str, url: str) -> None:
        self.hass = hass
        self.session = async_get_clientsession(hass)
        self.url = server
        self.rest_client = Go2RtcRestClient(self.session, server)

        if "://" in url:
            self.stream_id = f"{DOMAIN}_{hashlib.md5(url.encode()).hexdigest()}"
            self.source = url
        else:
            self.stream_id = url
            self.source = None

    @property
    def domain(self) -> str:
        return DOMAIN

    @callback
    def async_is_supported(self, stream_source: str) -> bool:
        return True

    async def async_handle_async_webrtc_offer(
        self,
        camera: Camera,
        offer_sdp: str,
        session_id: str,
        send_message: WebRTCSendMessage,
    ) -> None:
        if self.source:
            await self.update_stream_source()

        ws_client = Go2RtcWsClient(self.session, self.url, source=self.stream_id)
        self._sessions[session_id] = ws_client

        @callback
        def on_messages(message: ReceiveMessages) -> None:
            value: WebRTCMessage
            match message:
                case WebRTCCandidate():
                    value = HAWebRTCCandidate(RTCIceCandidateInit(message.candidate))
                case WebRTCAnswer():
                    value = HAWebRTCAnswer(message.sdp)
                case WsError():
                    value = WebRTCError("go2rtc_webrtc_offer_failed", message.error)

            send_message(value)

        ws_client.subscribe(on_messages)
        config = camera.async_get_webrtc_client_configuration()
        await ws_client.send(WebRTCOffer(offer_sdp, config.configuration.ice_servers))

    async def async_on_webrtc_candidate(
        self, session_id: str, candidate: RTCIceCandidateInit
    ) -> None:
        if session_info := self._sessions.get(session_id):
            await session_info.send(WebRTCCandidate(candidate.candidate))

    @callback
    def async_close_session(self, session_id: str) -> None:
        if session_info := self._sessions.pop(session_id, None):
            self.hass.async_create_task(session_info.close())

    async def async_get_image(
        self,
        camera: Camera,
        width: int | None = None,
        height: int | None = None,
    ) -> bytes | None:
        if self.source:
            await self.update_stream_source()
        return await self.rest_client.get_jpeg_snapshot(self.stream_id, width, height)

    async def update_stream_source(self) -> None:
        streams = await self.rest_client.streams.list()
        stream = streams.get(self.stream_id)
        if not stream or self.source not in stream.producers:
            await self.rest_client.streams.add(self.stream_id, [self.source])

    async def rtsp_url(self) -> str:
        try:
            # noinspection protected-member
            resp = await self.rest_client._client.request("GET", "/api")
            info = await resp.json()
            host = re.search(r"^[^:]+", info["host"])[0]  # noqa
            port = re.search(r"[0-9]+$", info["rtsp"]["listen"])[0]  # noqa
            return f"rtsp://{host}:{port}/{self.stream_id}"
        except Exception as e:
            raise HomeAssistantError(f"Can't get rtsp address: {e}")
