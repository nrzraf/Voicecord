import asyncio
import json
import os
import sys
import requests
import websockets

TOKEN = os.getenv("DISCORD_TOKEN", "")
GUILD_ID = os.getenv("GUILD_ID", "")
CHANNEL_ID = os.getenv("CHANNEL_ID", "")

STATUS = os.getenv("STATUS", "idle")

# Konversi String ke Boolean Python sejati
SELF_MUTE = os.getenv("SELF_MUTE", "true").lower() == "true"
SELF_DEAF = os.getenv("SELF_DEAF", "true").lower() == "true"

API = "https://discord.com/api/v10"

res = requests.get(f"{API}/users/@me", headers={"Authorization": TOKEN})
if res.status_code != 200:
    print("Invalid token! Periksa kembali token di Environment Variables.")
    sys.exit(1)

user = res.json()
print(f"Logged in as {user['username']} ({user['id']})!")


async def heartbeat(ws, interval):
    """Menjaga koneksi WebSocket tetap hidup."""
    try:
        while True:
            await asyncio.sleep(interval / 1000)
            await ws.send(json.dumps({"op": 1, "d": None}))
    except Exception:
        pass


async def keep_in_voice(ws):
    """
    Tugas latar belakang untuk memastikan akun selalu tetap berada di voice channel.
    Mengirim ulang permintaan join setiap 20 detik jika akun terpental/disconnect.
    """
    try:
        while True:
            await ws.send(
                json.dumps(
                    {
                        "op": 4,
                        "d": {
                            "guild_id": GUILD_ID,
                            "channel_id": CHANNEL_ID,
                            "self_mute": SELF_MUTE,
                            "self_deaf": SELF_DEAF,
                        },
                    }
                )
            )
            # Mengirim ulang paket join setiap 20 detik
            await asyncio.sleep(20)
    except Exception:
        pass


async def main():
    uri = "wss://gateway.discord.gg/?v=10&encoding=json"

    async with websockets.connect(uri, max_size=10 * 1024 * 1024) as ws:
        hello = json.loads(await ws.recv())
        heartbeat_interval = hello["d"]["heartbeat_interval"]

        # Jalankan Heartbeat
        heartbeat_task = asyncio.create_task(
            heartbeat(ws, heartbeat_interval)
        )

        # Send Identify Payload
        await ws.send(
            json.dumps(
                {
                    "op": 2,
                    "d": {
                        "token": TOKEN,
                        "properties": {
                            "$os": "windows",
                            "$browser": "chrome",
                            "$device": "pc",
                        },
                        "presence": {"status": STATUS, "afk": False},
                    },
                }
            )
        )

        # Tunggu sampai mendapat event READY
        while True:
            msg = await ws.recv()
            event = json.loads(msg)
            if event.get("t") == "READY":
                break

        print("Connected to Discord Gateway! Starting Voice Keep-Alive...")

        # Jalankan task rutin untuk menjaga akun tetap berada di Voice Channel
        voice_task = asyncio.create_task(keep_in_voice(ws))

        try:
            while True:
                await ws.recv()
        except websockets.exceptions.ConnectionClosed as e:
            print(f"WebSocket closed ({e.code}): Reconnecting in 5s...")
        finally:
            heartbeat_task.cancel()
            voice_task.cancel()


async def run():
    while True:
        try:
            await main()
        except Exception as e:
            print("Error/Disconnected:", e)

        print("Attempting to reconnect in 5 seconds...")
        await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(run())
