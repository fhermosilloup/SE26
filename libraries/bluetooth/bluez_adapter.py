# bluez_adapter.py
"""
    Dependencies:
        - dbus-next: pip install dbus-next
        - bluez:
                systemctl status bluetooth  # Check if driver is installed/enabled
                sudo apt install bluez      # If not, install it
                sudo systemctl enable --now bluetooth # If driver is disabled, enable it
        - rfcomm:
            sudo visudo -f /etc/sudoers.d/rfcomm # add root privilegies to rfcomm command
            REPLACE_WITH_YOUR_USERNAME ALL=(root) NOPASSWD: /usr/bin/rfcomm  # add this to the file


"""
import asyncio
import re

from dataclasses import dataclass

from dbus_next import BusType, Variant
from dbus_next.aio import MessageBus

import os
import shutil
import subprocess


BLUEZ_SERVICE = "org.bluez"
ADAPTER_INTERFACE = "org.bluez.Adapter1"
DEVICE_INTERFACE = "org.bluez.Device1"
PROPERTIES_INTERFACE = "org.freedesktop.DBus.Properties"
OBJECT_MANAGER_INTERFACE = "org.freedesktop.DBus.ObjectManager"


# Bluetooth Device
@dataclass
class BluetoothDevice:
    """
    Representa un dispositivo Bluetooth conocido por BlueZ.

    Attributes
    ----------
    name : str
        Nombre anunciado por el dispositivo.

    mac : str
        Dirección MAC Bluetooth.

    paired : bool
        Indica si el dispositivo está emparejado.

    trusted : bool
        Indica si BlueZ considera confiable al dispositivo.

    connected : bool
        Indica si BlueZ reporta actualmente una conexión.

    rssi : int | None
        Intensidad de señal recibida en dBm.
        Puede ser None si BlueZ no dispone del dato.
    """

    name: str
    mac: str

    paired: bool = False
    trusted: bool = False
    connected: bool = False

    rssi: int | None = None


# Bluetooth Adapter
class BluetoothAdapter:
    """
    Interfaz para administrar Bluetooth mediante BlueZ:
        - Encendido/apagado del adaptador.
        - Escaneo de dispositivos.
        - Emparejamiento.
        - Estado Trusted.
        - Consulta de dispositivos emparejados.

    La transferencia de datos Bluetooth no se realiza aquí.
    Para comunicación RFCOMM se recomienda utilizar socket.

    Example
    -------
    bt = BluetoothAdapter()

    bt.power = True

    devices = bt.scan()

    bt.pair(
        name="ESP32_BT",
        trust=True
    )
    """

    MAC_PATTERN = re.compile(
        r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$"
    )


    # Constructor
    def __init__(self):
        """
        Inicializa el adaptador Bluetooth.

        Al crear el objeto:

            1. Busca automáticamente un Adapter1 de BlueZ.
            2. Consulta si se encuentra encendido.
            3. Guarda el estado en self._power.

        Raises
        ------
        RuntimeError
            Si BlueZ no encuentra ningún adaptador Bluetooth.
        """

        self._adapter_path = None
        self._power = False

        # Localizar adaptador
        self._adapter_path = self._run( self._find_adapter() )

        if self._adapter_path is None:
            raise RuntimeError("No se encontró ningún adaptador Bluetooth")

        # Leer estado inicial
        self._power = self._run( self._read_power() )

    @property
    def discoverable(self):
        """
        Indica si el adaptador es visible para otros dispositivos.
        """

        return self._run( self._read_adapter_property("Discoverable") )


    @discoverable.setter
    def discoverable(self, state):
        """
        Activa o desactiva la visibilidad Bluetooth.
        """

        if not isinstance(state, bool):
            raise TypeError("discoverable debe ser True o False")

        self._run( self._set_adapter_property("Discoverable", Variant("b", state)) )

    @property
    def alias(self):
        return self._run(self._read_adapter_property("Alias"))
    @alias.setter
    def alias(self, name):
        """
        Establece el alias de raspberry pi como dispositivo bluetooth
        """

        if not isinstance(name,str):
            raise TypeError("pairable debe ser una string")

        self._run(self._set_adapter_property("Alias", Variant("s",state)))

    @property
    def pairable(self):
        """
        Indica si otros dispositivos pueden solicitar pairing.
        """

        return self._run( self._read_adapter_property("Pairable") )


    @pairable.setter
    def pairable(self, state):
        """
        Permite o impide solicitudes de emparejamiento.
        """

        if not isinstance(state, bool):
            raise TypeError("pairable debe ser True o False")

        self._run( self._set_adapter_property("Pairable", Variant("b", state)) )

    @property
    def address(self):
        return self._run(self._read_address())
    
    @property
    def power(self):
        """
        Estado actual del adaptador.

        Returns
        -------
        bool

        Example
        -------
        print(bt.power)
        """

        # Actualizar valor desde BlueZ
        self._power = self._run(
            self._read_power()
        )

        return self._power

    @power.setter
    def power(self, state):
        """
        Enciende o apaga el adaptador Bluetooth.

        Parameters
        ----------
        state : bool

        Example
        -------
        bt.power = True

        bt.power = False
        """

        if not isinstance(state, bool):
            raise TypeError("power solamente acepta True o False")
        
        self._run(self._set_power(state))
        self._power = state
    
    @property
    def devices(self):
        """
        Lista los dispositivos actualmente emparejados.

        No inicia un nuevo escaneo.

        Returns
        -------
        list[BluetoothDevice]

        Example
        -------
        for device in bt.paired_devices:

            print(device.name)
            print(device.mac)
            print(device.trusted)
            print(device.connected)
        """

        return self._run(self._paired_devices() )
        
        
    def scan(self, duration=5):
        """
        Escanea dispositivos Bluetooth cercanos.

        Si Bluetooth se encuentra apagado,
        se enciende automáticamente.

        Parameters
        ----------
        duration : float
            Tiempo de escaneo en segundos.

        Returns
        -------
        list[BluetoothDevice]

        Example
        -------
        devices = bt.scan(5)

        for device in devices:

            print(
                device.name,
                device.mac
            )
        """

        if duration <= 0:
            raise ValueError("duration debe ser mayor que 0")

        if not self.power:
            self.power = True

        return self._run(self._scan(duration))
            
    
    def pair(self, device, trust=True):
        """
        Empareja un dispositivo Bluetooth.

        Parameters
        ----------
        device : BluetoothDevice
            Dispositivo obtenido mediante scan().

        trust : bool
            Si True, marca el dispositivo como Trusted.

        Returns
        -------
        bool
            True si el dispositivo quedó emparejado correctamente.
        """

        if not isinstance(device, BluetoothDevice):
            raise TypeError("device debe ser un BluetoothDevice")

        if not isinstance(trust, bool):
            raise TypeError("trust debe ser True o False")

        if not self.power:
            self.power = True

        # Emparejar
        success = self._run( self._pair_device(device.mac) )

        if not success:
            return False

        # Establecer Trusted en una operación independiente
        success = self._run( self._set_device_trusted(device.mac, trust) )

        if success:
            # Actualizar también el objeto local
            device.paired = True
            device.trusted = trust

        return success




    def bind(self, device, channel=1, rfcomm=None):
        """
        Crea un dispositivo serial RFCOMM asociado a un
        BluetoothDevice.

        Parameters
        ----------
        device : BluetoothDevice
            Dispositivo Bluetooth remoto.

        channel : int
            Canal RFCOMM remoto.
            Para dispositivos SPP normalmente es 1.

        rfcomm : int | None
            Número del dispositivo RFCOMM local.

            rfcomm=0 -> /dev/rfcomm0
            rfcomm=1 -> /dev/rfcomm1

            Si es None, se busca automáticamente uno libre.

        Returns
        -------
        str | None
            Ruta del dispositivo creado, por ejemplo:

                /dev/rfcomm0

            Devuelve None si no pudo realizarse el bind.

        Example
        -------
        port = bt.bind(device)

        print(port)

        # /dev/rfcomm0
        """

        # Validar dispositivo
        if not isinstance(device, BluetoothDevice):
            raise TypeError("device debe ser un BluetoothDevice")

        # Validar canal
        if not isinstance(channel, int):
            raise TypeError("channel debe ser int")

        if channel <= 0:
            raise ValueError("channel debe ser mayor que 0")

        # Verificar utilidad rfcomm
        if shutil.which("rfcomm") is None:
            raise RuntimeError("La utilidad 'rfcomm' no está instalada")

        # Buscar rfcomm libre
        if rfcomm is None:
            rfcomm = self._find_free_rfcomm()

            if rfcomm is None:
                raise RuntimeError("No se encontró un dispositivo RFCOMM libre")

        else:

            if not isinstance(rfcomm,int):
                raise TypeError("rfcomm debe ser int o None")

            if rfcomm < 0:
                raise ValueError("rfcomm no puede ser negativo")

        port = f"/dev/rfcomm{rfcomm}"

        # Crear binding
        try:
            result = subprocess.run(
                [
                    "sudo",
                    "-n",
                    "rfcomm",
                    "bind",
                    str(rfcomm),
                    device.mac,
                    str(channel)
                ],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                print(result.returncode)
                print(result.stderr)
                return None

            return port

        except OSError:
            return None

    # Unpair device
    def unpair(self, device):
        """
        Elimina el vínculo de un dispositivo Bluetooth.

        Parameters
        ----------
        device : BluetoothDevice
            Dispositivo obtenido mediante scan() o devices.

        Returns
        -------
        bool
            True si el dispositivo fue eliminado correctamente.
            False en caso contrario.

        Example
        -------
        for device in bt.devices:

            if device.name == "ESP32_BT":

                bt.unpair(
                    device
                )
        """

        if not isinstance(device, BluetoothDevice):
            raise TypeError("device debe ser un BluetoothDevice")

        return self._run( self._unpair_device(device.mac) )

    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
        
        
        
        
        
    
    
    
    
    
    # Private methods =====================================================
    # Ejecutar funciones async internamente
    @staticmethod
    def _run(coroutine):
        """
        Ejecuta internamente una función asynchronous.

        Esto permite que la API pública sea síncrona y sencilla.
        """

        return asyncio.run(coroutine)


    # Object Manager
    async def _get_objects(self, bus):
        """
        Obtiene todos los objetos administrados por BlueZ.
        """

        introspection = await bus.introspect(
            BLUEZ_SERVICE,
            "/"
        )

        obj = bus.get_proxy_object(
            BLUEZ_SERVICE,
            "/",
            introspection
        )

        manager = obj.get_interface(
            OBJECT_MANAGER_INTERFACE
        )

        return await manager.call_get_managed_objects()


    # Detectar adaptador automáticamente
    async def _find_adapter(self):
        """
        Busca el primer dispositivo que implemente Adapter1.

        Normalmente será:

            /org/bluez/hci0
        """

        bus = await MessageBus(
            bus_type=BusType.SYSTEM
        ).connect()

        objects = await self._get_objects(bus)

        adapter_path = None

        for path, interfaces in objects.items():

            if ADAPTER_INTERFACE in interfaces:

                adapter_path = path
                break

        bus.disconnect()

        return adapter_path


    # Obtener objeto Adapter
    async def _get_adapter_object(
        self,
        bus
    ):

        introspection = await bus.introspect(
            BLUEZ_SERVICE,
            self._adapter_path
        )

        return bus.get_proxy_object(
            BLUEZ_SERVICE,
            self._adapter_path,
            introspection
        )

    async def _read_adapter_property(
        self,
        property_name
    ):

        bus = await MessageBus(
            bus_type=BusType.SYSTEM
        ).connect()

        adapter = await self._get_adapter_object(
            bus
        )

        properties = adapter.get_interface(
            PROPERTIES_INTERFACE
        )

        value = await properties.call_get(
            ADAPTER_INTERFACE,
            property_name
        )

        bus.disconnect()

        return value.value

    async def _set_adapter_property(
        self,
        property_name,
        value
    ):
        """
        Modifica una propiedad del Adapter1 de BlueZ.
        """

        bus = await MessageBus(
            bus_type=BusType.SYSTEM
        ).connect()

        adapter = await self._get_adapter_object(
            bus
        )

        properties = adapter.get_interface(
            PROPERTIES_INTERFACE
        )

        await properties.call_set(
            ADAPTER_INTERFACE,
            property_name,
            value
        )

        bus.disconnect()

    async def _read_address(self):
        bus = await MessageBus(bus_type=BusType.SYSTEM).connect()

        adapter = await self._get_adapter_object(bus)

        properties = adapter.get_interface(PROPERTIES_INTERFACE)

        value = await properties.call_get(ADAPTER_INTERFACE,"Address")

        bus.disconnect()

        return value.value

    
    

    async def _read_power(self):

        bus = await MessageBus(
            bus_type=BusType.SYSTEM
        ).connect()

        adapter = await self._get_adapter_object(
            bus
        )

        properties = adapter.get_interface(
            PROPERTIES_INTERFACE
        )

        value = await properties.call_get(
            ADAPTER_INTERFACE,
            "Powered"
        )

        bus.disconnect()

        return value.value

    async def _set_power(
        self,
        state
    ):

        bus = await MessageBus(
            bus_type=BusType.SYSTEM
        ).connect()

        adapter = await self._get_adapter_object(
            bus
        )

        properties = adapter.get_interface(
            PROPERTIES_INTERFACE
        )

        await properties.call_set(
            ADAPTER_INTERFACE,
            "Powered",
            Variant(
                "b",
                state
            )
        )

        bus.disconnect()


    # Convertir estructura BlueZ → BluetoothDevice
    @staticmethod
    def _parse_device(data):
        """
        Convierte las propiedades Device1 de BlueZ
        en un BluetoothDevice.
        """

        name_data = data.get("Name")
        alias_data = data.get("Alias")

        if name_data:
            name = name_data.value
        elif alias_data:
            name = alias_data.value
        else:
            name = "Unknown"

        mac = data["Address"].value
        paired = data.get("Paired")
        trusted = data.get("Trusted")
        connected = data.get("Connected")

        rssi = data.get("RSSI")

        return BluetoothDevice(
            name=name,
            mac=mac,

            paired=(
                paired.value
                if paired
                else False
            ),

            trusted=(
                trusted.value
                if trusted
                else False
            ),

            connected=(
                connected.value
                if connected
                else False
            ),

            rssi=(
                rssi.value
                if rssi
                else None
            )
        )


    
    

    async def _scan(
        self,
        duration
    ):

        bus = await MessageBus(
            bus_type=BusType.SYSTEM
        ).connect()

        adapter_obj = await self._get_adapter_object(
            bus
        )

        adapter = adapter_obj.get_interface(
            ADAPTER_INTERFACE
        )

        # Iniciar búsqueda
        await adapter.call_start_discovery()

        await asyncio.sleep(
            duration
        )

        await adapter.call_stop_discovery()

        # Leer dispositivos
        objects = await self._get_objects(
            bus
        )

        devices = []

        for path, interfaces in objects.items():

            if DEVICE_INTERFACE not in interfaces:
                continue

            data = interfaces[
                DEVICE_INTERFACE
            ]

            devices.append(
                self._parse_device(
                    data
                )
            )

        bus.disconnect()

        return devices


    
    

    async def _paired_devices(self):

        bus = await MessageBus(
            bus_type=BusType.SYSTEM
        ).connect()

        objects = await self._get_objects(
            bus
        )

        devices = []

        for path, interfaces in objects.items():

            if DEVICE_INTERFACE not in interfaces:
                continue

            data = interfaces[
                DEVICE_INTERFACE
            ]

            paired = data.get(
                "Paired"
            )

            # Sólo dispositivos vinculados
            if (
                paired is None
                or not paired.value
            ):

                continue

            devices.append(
                self._parse_device(
                    data
                )
            )

        bus.disconnect()

        return devices


    # Buscar dispositivo
    async def _find_device_path(
        self,
        bus,
        mac
    ):
        """
        Busca el path Device1 asociado a una MAC.
        """

        objects = await self._get_objects(
            bus
        )

        for path, interfaces in objects.items():

            if DEVICE_INTERFACE not in interfaces:
                continue

            data = interfaces[
                DEVICE_INTERFACE
            ]

            address = data[
                "Address"
            ].value

            if (
                address.upper()
                == mac.upper()
            ):

                return path

        return None

    async def _pair_device(
        self,
        mac
    ):

        bus = await MessageBus(
            bus_type=BusType.SYSTEM
        ).connect()

        try:

            device_path = await self._find_device_path(
                bus,
                mac
            )

            if device_path is None:

                bus.disconnect()
                return False

            introspection = await bus.introspect(
                BLUEZ_SERVICE,
                device_path
            )

            obj = bus.get_proxy_object(
                BLUEZ_SERVICE,
                device_path,
                introspection
            )

            device = obj.get_interface(
                DEVICE_INTERFACE
            )

            properties = obj.get_interface(
                PROPERTIES_INTERFACE
            )

            # Verificar si ya está emparejado
            paired = await properties.call_get(
                DEVICE_INTERFACE,
                "Paired"
            )

            if not paired.value:

                await device.call_pair()

            # Confirmar estado
            paired = await properties.call_get(
                DEVICE_INTERFACE,
                "Paired"
            )

            bus.disconnect()

            return paired.value

        except Exception as error:

            print(
                "PAIR ERROR:",
                error
            )

            bus.disconnect()

            return False


    async def _set_device_trusted(
        self,
        mac,
        state
    ):
        """
        Cambia la propiedad Trusted de un dispositivo Bluetooth.
        """

        bus = await MessageBus(
            bus_type=BusType.SYSTEM
        ).connect()

        try:

            # Buscar nuevamente el dispositivo
            device_path = await self._find_device_path(
                bus,
                mac
            )

            if device_path is None:

                bus.disconnect()
                return False

            # Obtener un proxy nuevo
            introspection = await bus.introspect(
                BLUEZ_SERVICE,
                device_path
            )

            obj = bus.get_proxy_object(
                BLUEZ_SERVICE,
                device_path,
                introspection
            )

            properties = obj.get_interface(
                PROPERTIES_INTERFACE
            )

            # Cambiar Trusted
            await properties.call_set(
                DEVICE_INTERFACE,
                "Trusted",
                Variant(
                    "b",
                    state
                )
            )

            # Leer nuevamente para verificar
            trusted = await properties.call_get(
                DEVICE_INTERFACE,
                "Trusted"
            )

            bus.disconnect()

            return trusted.value == state

        except Exception as error:

            print(
                "TRUST ERROR:",
                error
            )

            bus.disconnect()

            return False


    async def _unpair_device(
        self,
        mac
    ):
        """
        Elimina de BlueZ el dispositivo asociado a una MAC.
        """

        bus = await MessageBus(
            bus_type=BusType.SYSTEM
        ).connect()

        try:
            # Buscar Device1
            device_path = await self._find_device_path(
                bus,
                mac
            )

            if device_path is None:

                bus.disconnect()

                return False

            # Obtener Adapter1
            adapter_obj = await self._get_adapter_object(
                bus
            )

            adapter = adapter_obj.get_interface(
                ADAPTER_INTERFACE
            )

            # Eliminar dispositivo
            await adapter.call_remove_device(
                device_path
            )

            bus.disconnect()

            return True

        except Exception:

            bus.disconnect()

            return False


    def _find_free_rfcomm(
        self,
        max_devices=32
    ):
        """
        Busca el primer /dev/rfcommX disponible.

        Returns
        -------
        int | None
            Índice RFCOMM libre.
        """

        for index in range(
            max_devices
        ):

            path = f"/dev/rfcomm{index}"

            if not os.path.exists(path):

                return index

        return None
