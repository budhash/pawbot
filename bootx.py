import uasyncio as asyncio
from NanoWeb import ConnectionManager 

async def main():
    event_loop = asyncio.get_event_loop()
    manager = ConnectionManager()
    success = await manager.boot(event_loop)
    if success:
        print("auto connect successful")
        manager.disable_ap()
    else:
        print("auto connect failed - starting access portal")
        (ap_ssid, ap_password, ap_ip) = manager.initialize_access_point(event_loop)
        event_loop.run_forever()
    
asyncio.run(main())