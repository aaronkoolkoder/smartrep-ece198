"""Best-effort local mDNS. Always retain a printed IP fallback."""
import logging
import socket
from zeroconf import ServiceInfo
from zeroconf.asyncio import AsyncZeroconf


async def advertise(addresses,port):
    usable=[address for address in addresses if not address.startswith('127.')]
    if not usable:
        return None
    service=ServiceInfo('_http._tcp.local.','SmartRep._http._tcp.local.',
                        addresses=[socket.inet_aton(address) for address in usable],
                        port=port,server='smartrep.local.',properties={'app':'smartrep'})
    publisher=AsyncZeroconf()
    try:
        await publisher.async_register_service(service)
        logging.info('Bridge discovery: smartrep.local:%s',port)
        return publisher
    except Exception:
        logging.warning('mDNS unavailable; use the LAN IP printed above.')
        await publisher.async_close()
        return None
