# services/health_check.py

import asyncio
from aiohttp import web

async def handle_health(request):
    # Можно добавить детали (статистика, usage, аптайм и т.д.)
    return web.json_response({"status": "ok", "message": "DailyCheck Bot работает!"})

def start_health_server(port=8080):
    app = web.Application()
    app.add_routes([web.get('/health', handle_health)])
    runner = web.AppRunner(app)
    loop = asyncio.get_event_loop()
    loop.create_task(_run_server(runner, port))

async def _run_server(runner, port):
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
