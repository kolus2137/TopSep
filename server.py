import asyncio
import os
import websockets

CLIENTS = set()


async def handler(websocket):
    print(f"[+] CLIENT CONNECTED: {websocket.remote_address}")
    CLIENTS.add(websocket)
    try:
        async for message in websocket:
            # Przekazuj wiadomość do wszystkich pozostałych połączonych klientów
            for client in CLIENTS:
                if client != websocket:
                    try:
                        await client.send(message)
                    except Exception as e:
                        print(f"[-] SEND ERROR: {e}")
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        print(f"[-] CLIENT DISCONNECTED: {websocket.remote_address}")
        CLIENTS.remove(websocket)


async def main():
    # Render automatycznie przekazuje port w zmiennej środowiskowej PORT
    port = int(os.environ.get("PORT", 10000))
    print(f"[ TOPSEP CORE SERVER // LISTENING ON PORT {port} ]")
    async with websockets.serve(handler, "0.0.0.0", port):
        await asyncio.Future()  # Działa 24/7


if __name__ == "__main__":
    asyncio.run(main())
