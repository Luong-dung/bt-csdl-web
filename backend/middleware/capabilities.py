"""Prevent caching permission responses, including handled errors and redirects."""

import re

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

PERMISSION_PATH = re.compile(
    r'/api/v1/(?:auth/capabilities|teams/managed|(?:teams|tournaments)/[^/]+/capabilities)/?'
)


class PermissionCacheMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope['type'] != 'http' or not PERMISSION_PATH.fullmatch(scope['path']):
            await self.app(scope, receive, send)
            return

        async def send_uncached(message: Message):
            if message['type'] == 'http.response.start':
                MutableHeaders(scope=message)['Cache-Control'] = 'private, no-store'
            await send(message)

        await self.app(scope, receive, send_uncached)
