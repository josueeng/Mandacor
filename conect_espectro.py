import binascii
import socket
import struct
import threading
import time
import xml.etree.ElementTree as ET
from typing import Optional

# ============================================================
# CONFIGURAÇÃO DO ESPECTROFOTÔMETRO
# ============================================================

DEVICE_IP = "192.168.1.13"
TCP_PORT = 6000

DISCOVERY_PORT = 6002
BROADCAST_IP = "192.168.1.1"

TCP_TIMEOUT = 12.0

MAGIC = b"GB\x03\x00"
XML_END = b"</CommandResult>"


# ============================================================
# CRC
# ============================================================

def crc16(data: bytes) -> bytes:
    """
    CRC-16/CCITT XMODEM
    Polinômio: 0x1021
    Init: 0x0000
    Saída: big-endian
    """
    return binascii.crc_hqx(data, 0).to_bytes(2, "big")


# ============================================================
# DESCOBERTA UDP
# ============================================================

def build_discovery_query(local_udp_port: int) -> bytes:
    """
    Pacote BYKQUERY observado na comunicação real.
    """
    return (
        b"BYKQUERY"
        + (b"\x00" * 10)
        + struct.pack("<H", 1)
        + struct.pack("<H", local_udp_port)
    )


class DiscoveryHeartbeat:
    """
    Faz a descoberta do aparelho via UDP e mantém o heartbeat
    BYKQUERY ativo durante a conexão TCP.
    """

    def __init__(self):
        self.sock: Optional[socket.socket] = None
        self.thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.local_port: Optional[int] = None
        self.last_response = None

    def start(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind(("0.0.0.0", 0))
        sock.settimeout(0.35)

        self.sock = sock
        self.local_port = sock.getsockname()[1]

        query = build_discovery_query(self.local_port)

        print("\n=== DESCOBERTA UDP ===")
        print("Porta UDP local:", self.local_port)
        print("BYKQUERY:", query.hex())

        found = False

        for _ in range(5):
            # Broadcast
            sock.sendto(query, (BROADCAST_IP, DISCOVERY_PORT))

            deadline = time.time() + 1.2

            while time.time() < deadline:
                try:
                    data, addr = sock.recvfrom(4096)
                except socket.timeout:
                    break

                if data.startswith(b"BYKINSTRUMENT"):
                    self.last_response = (data, addr)

                    print("BYKINSTRUMENT recebido de:", addr)
                    print("Bytes:", len(data))

                    found = True
                    break

            if found:
                break

            # Tentativa unicast de fallback
            try:
                sock.sendto(query, (DEVICE_IP, DISCOVERY_PORT))
            except OSError:
                pass

        if not found:
            sock.close()
            self.sock = None

            raise RuntimeError(
                "O espectrofotômetro não respondeu ao BYKQUERY na porta UDP 6002."
            )

        self.thread = threading.Thread(
            target=self._heartbeat_worker,
            args=(query,),
            daemon=True,
        )

        self.thread.start()

    def _heartbeat_worker(self, query: bytes):
        """
        Mantém BYKQUERY sendo enviado aproximadamente a cada 1 segundo.
        """
        if self.sock is None:
            return

        while not self.stop_event.is_set():
            try:
                self.sock.sendto(
                    query,
                    (BROADCAST_IP, DISCOVERY_PORT),
                )

                end = time.time() + 0.45

                while time.time() < end:
                    if self.stop_event.is_set():
                        return

                    try:
                        data, addr = self.sock.recvfrom(4096)
                    except socket.timeout:
                        break

                    if data.startswith(b"BYKINSTRUMENT"):
                        self.last_response = (data, addr)
                        break

            except OSError:
                break

            self.stop_event.wait(0.55)

    def close(self):
        self.stop_event.set()

        if self.thread is not None:
            self.thread.join(timeout=1.5)

        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass


# ============================================================
# PROTOCOLO TCP BYK
# ============================================================

def make_header(command_id: int) -> bytes:
    """
    Cabeçalho BYK de 32 bytes.
    """
    return (
        MAGIC
        + struct.pack("<I", 0)
        + struct.pack("<I", 1)
        + struct.pack("<I", 11)
        + struct.pack("<I", 0)
        + struct.pack("<I", command_id)
        + struct.pack("<I", 0)
        + struct.pack("<I", 0xFFFFFFFF)
    )


def build_request(
    command_id: int,
    name: str,
    parameters: Optional[str] = None,
):
    """
    Monta cabeçalho + XML + CRC.
    """

    header = make_header(command_id)

    if parameters is None:
        xml = (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            f'<Command Id="{command_id}" '
            f'Name="{name}" '
            'DestinationId="11" />'
        ).encode("utf-8")

    else:
        xml = (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            f'<Command Id="{command_id}" '
            f'Name="{name}" '
            'DestinationId="11">\r\n'
            '  <Parameters>\r\n'
            f'{parameters}'
            '  </Parameters>\r\n'
            '</Command>'
        ).encode("utf-8")

    checksum = crc16(header + xml)

    return header, xml + checksum


def recv_exact(sock: socket.socket, size: int) -> bytes:
    """
    Recebe exatamente 'size' bytes.
    """

    data = bytearray()

    while len(data) < size:
        chunk = sock.recv(size - len(data))

        if not chunk:
            raise ConnectionError(
                "Conexão TCP encerrada pelo espectrofotômetro."
            )

        data.extend(chunk)

    return bytes(data)


def validate_crc(
    header: bytes,
    payload: bytes,
    received_crc: bytes,
):
    expected_crc = crc16(header + payload)

    if received_crc != expected_crc:
        raise ValueError(
            "CRC inválido. "
            f"Recebido={received_crc.hex()} "
            f"Esperado={expected_crc.hex()}"
        )


def recv_message(sock: socket.socket):
    """
    Recebe uma mensagem do protocolo BYK.
    Pode ser:
    - ACK
    - resposta XML
    """

    header = recv_exact(sock, 32)

    if header[:4] != MAGIC:
        raise ValueError(
            "Magic inesperado: "
            + header[:8].hex()
        )

    flags = struct.unpack_from("<I", header, 4)[0]
    command_id = struct.unpack_from("<I", header, 20)[0]

    # ACK de aplicação
    if flags & 0x1000:
        received_crc = recv_exact(sock, 2)

        validate_crc(
            header,
            b"",
            received_crc,
        )

        return {
            "type": "ack",
            "command_id": command_id,
            "xml": None,
        }

    # Resposta XML
    body = bytearray()

    while XML_END not in body:
        chunk = sock.recv(4096)

        if not chunk:
            raise ConnectionError(
                "Conexão encerrada durante a resposta XML."
            )

        body.extend(chunk)

    xml_end = (
        body.index(XML_END)
        + len(XML_END)
    )

    while len(body) < xml_end + 2:
        body.extend(
            recv_exact(
                sock,
                xml_end + 2 - len(body),
            )
        )

    xml = bytes(
        body[:xml_end]
    )

    received_crc = bytes(
        body[xml_end:xml_end + 2]
    )

    validate_crc(
        header,
        xml,
        received_crc,
    )

    return {
        "type": "data",
        "command_id": command_id,
        "xml": xml,
    }


def transact(
    sock: socket.socket,
    command_id: int,
    name: str,
    parameters: Optional[str] = None,
):
    """
    Envia uma requisição seguindo o fluxo real observado:
    1) envia header de 32 bytes
    2) espera 200 ms
    3) envia XML + CRC
    4) espera ACK
    5) espera CommandResult XML
    """

    header, body = build_request(
        command_id,
        name,
        parameters,
    )

    print(
        f"\nTX {name} "
        f"(ID {command_id})"
    )

    print(
        "  header:",
        len(header),
        "bytes",
    )

    print(
        "  corpo :",
        len(body),
        "bytes",
    )

    print(
        "  crc   :",
        body[-2:].hex(),
    )

    sock.sendall(header)

    time.sleep(0.20)

    sock.sendall(body)

    for _ in range(4):
        msg = recv_message(sock)

        print(
            f"  RX {msg['type']} "
            f"cmd={msg['command_id']}"
        )

        if msg["type"] == "data":
            return msg["xml"]

    raise RuntimeError(
        "Não chegou resposta XML do aparelho."
    )


# ============================================================
# PARSER XML
# ============================================================

def parse_values(xml_bytes: bytes):
    root = ET.fromstring(
        xml_bytes.decode("utf-8")
    )

    values = {}

    for elem in root.findall(".//*[@Name]"):
        if "Value" in elem.attrib:
            values[
                elem.attrib["Name"]
            ] = elem.attrib["Value"]

    return root, values


# ============================================================
# COMANDOS
# ============================================================

def get_instrument_info(
    sock: socket.socket,
):
    xml = transact(
        sock,
        4,
        "GetInstrumentInfo",
    )

    _, values = parse_values(xml)

    return values


def get_measurement_ids(
    sock: socket.socket,
):
    xml = transact(
        sock,
        143,
        "RetrieveMeasurementIdList",
    )

    root = ET.fromstring(
        xml.decode("utf-8")
    )

    measurements = []

    for elem in root.findall(".//Guid"):
        measurements.append(
            {
                "id": int(
                    elem.attrib["Id"]
                ),
                "name": elem.attrib.get(
                    "Name",
                    "",
                ),
                "guid": elem.attrib.get(
                    "Value",
                    "",
                ),
            }
        )

    return measurements


def retrieve_measurement(
    sock: socket.socket,
    record_id: int,
):
    """
    Busca uma leitura pelo JobListRecordId.
    """

    parameters = (
        '    <ParameterInt32 '
        'Name="JobListRecordId" '
        f'Value="{record_id}" />\r\n'
    )

    xml = transact(
        sock,
        42,
        "RetrieveMeasurement",
        parameters,
    )

    root = ET.fromstring(
        xml.decode("utf-8")
    )

    # Verifica Result
    result = root.find(
        './/*[@Name="Result"]'
    )

    if (
        result is not None
        and result.attrib.get("Value") != "OK"
    ):
        return (
            None,
            result.attrib.get(
                "Description",
                "NOK",
            ),
        )

    measure = root.find(
        ".//MeasureValue"
    )

    if measure is None:
        return (
            None,
            "Resposta sem MeasureValue",
        )

    # --------------------------------------------------------
    # LAB bruto
    # --------------------------------------------------------

    lab = {}

    for elem in root.findall(
        './/DataValueCollection'
        '[@Name="LAB"]/ScaleValue'
    ):
        lab[
            elem.attrib["Name"]
        ] = float(
            elem.attrib["Value"]
        )

    # --------------------------------------------------------
    # Organiza LAB por ângulo
    # --------------------------------------------------------

    angles = {}

    for angle in (
        15,
        25,
        45,
        75,
        105,
    ):
        angles[angle] = {
            "L": lab.get(
                f"L* {angle}"
            ),
            "a": lab.get(
                f"a* {angle}"
            ),
            "b": lab.get(
                f"b* {angle}"
            ),
        }

    # --------------------------------------------------------
    # Temperatura do aparelho
    # --------------------------------------------------------

    temperature = None

    temp_elem = root.find(
        './/*[@Name="DeviceTemperature"]'
    )

    if temp_elem is not None:
        try:
            temperature = float(
                temp_elem.attrib["Value"]
            )
        except (TypeError, ValueError):
            temperature = None

    # --------------------------------------------------------
    # Resultado final
    # --------------------------------------------------------

    measurement = {
        "id": int(
            measure.attrib["Id"]
        ),

        "name": measure.attrib.get(
            "Name"
        ),

        "timestamp": measure.attrib.get(
            "TimeStamp"
        ),

        "guid": measure.attrib.get(
            "Guid"
        ),

        "temperature": temperature,

        "angles": angles,

        # Mantém também o LAB original
        "lab_raw": lab,
    }

    return measurement, None


# ============================================================
# FUNÇÕES PARA PEGAR DADOS SEPARADOS
# ============================================================

def get_L(
    measurement: dict,
    angle: int,
):
    return measurement[
        "angles"
    ][angle]["L"]


def get_a(
    measurement: dict,
    angle: int,
):
    return measurement[
        "angles"
    ][angle]["a"]


def get_b(
    measurement: dict,
    angle: int,
):
    return measurement[
        "angles"
    ][angle]["b"]


def get_lab(
    measurement: dict,
    angle: int,
):
    """
    Retorna L*, a*, b* de um ângulo.
    """

    return measurement[
        "angles"
    ][angle]


# ============================================================
# EXIBIÇÃO
# ============================================================

def print_measurement(
    measurement: dict,
):
    print(
        "\n=== ÚLTIMA LEITURA VÁLIDA ==="
    )

    print(
        "ID:",
        measurement["id"],
    )

    print(
        "Nome:",
        measurement["name"],
    )

    print(
        "Data:",
        measurement["timestamp"],
    )

    if measurement["temperature"] is not None:
        print(
            "Temperatura:",
            f'{measurement["temperature"]:.2f} °C',
        )

    print(
        f'\n'
        f'{"Ângulo":>7} '
        f'{"L*":>12} '
        f'{"a*":>12} '
        f'{"b*":>12}'
    )

    for angle in (
        15,
        25,
        45,
        75,
        105,
    ):
        data = measurement[
            "angles"
        ][angle]

        L = data["L"]
        a = data["a"]
        b = data["b"]

        if (
            L is None
            or a is None
            or b is None
        ):
            print(
                f"{angle:>6}° "
                "[LAB ausente]"
            )

        else:
            print(
                f"{angle:>6}° "
                f"{L:>12.4f} "
                f"{a:>12.4f} "
                f"{b:>12.4f}"
            )


def print_individual_values(
    measurement: dict,
):
    """
    Exemplo de acesso individual a cada valor.
    """

    print(
        "\n=== DADOS SEPARADOS ==="
    )

    L15 = get_L(
        measurement,
        15,
    )

    a15 = get_a(
        measurement,
        15,
    )

    b15 = get_b(
        measurement,
        15,
    )

    L25 = get_L(
        measurement,
        25,
    )

    a25 = get_a(
        measurement,
        25,
    )

    b25 = get_b(
        measurement,
        25,
    )

    L45 = get_L(
        measurement,
        45,
    )

    a45 = get_a(
        measurement,
        45,
    )

    b45 = get_b(
        measurement,
        45,
    )

    L75 = get_L(
        measurement,
        75,
    )

    a75 = get_a(
        measurement,
        75,
    )

    b75 = get_b(
        measurement,
        75,
    )

    L105 = get_L(
        measurement,
        105,
    )

    a105 = get_a(
        measurement,
        105,
    )

    b105 = get_b(
        measurement,
        105,
    )

    print(
        "L 15° =",
        L15,
    )

    print(
        "a 15° =",
        a15,
    )

    print(
        "b 15° =",
        b15,
    )

    print(
        "L 25° =",
        L25,
    )

    print(
        "a 25° =",
        a25,
    )

    print(
        "b 25° =",
        b25,
    )

    print(
        "L 45° =",
        L45,
    )

    print(
        "a 45° =",
        a45,
    )

    print(
        "b 45° =",
        b45,
    )

    print(
        "L 75° =",
        L75,
    )

    print(
        "a 75° =",
        a75,
    )

    print(
        "b 75° =",
        b75,
    )

    print(
        "L 105° =",
        L105,
    )

    print(
        "a 105° =",
        a105,
    )

    print(
        "b 105° =",
        b105,
    )


# ============================================================
# BUSCA DA ÚLTIMA LEITURA VÁLIDA
# ============================================================

def get_latest_measurement(
    sock: socket.socket,
):
    ids = get_measurement_ids(sock)

    print(
        "\nRegistros listados:",
        len(ids),
    )

    if not ids:
        raise RuntimeError(
            "Nenhuma medição armazenada."
        )

    # Começa pelo maior ID.
    # Se houver registro órfão/corrompido,
    # tenta o ID anterior.
    for item in sorted(
        ids,
        key=lambda x: x["id"],
        reverse=True,
    ):
        measurement, error = (
            retrieve_measurement(
                sock,
                item["id"],
            )
        )

        if measurement is not None:
            return measurement

        print(
            f'Ignorando '
            f'{item["name"]} '
            f'/ ID {item["id"]}: '
            f'{error}'
        )

    raise RuntimeError(
        "Nenhuma medição válida recuperada."
    )


# ============================================================
# MAIN
# ============================================================

def main():
    discovery = DiscoveryHeartbeat()

    try:
        # ----------------------------------------------------
        # 1. DESCOBRE O APARELHO
        # ----------------------------------------------------

        discovery.start()

        time.sleep(0.35)

        # ----------------------------------------------------
        # 2. ABRE CONEXÃO TCP
        # ----------------------------------------------------

        print(
            f"\nConectando a "
            f"{DEVICE_IP}:{TCP_PORT}..."
        )

        with socket.create_connection(
            (
                DEVICE_IP,
                TCP_PORT,
            ),
            timeout=TCP_TIMEOUT,
        ) as sock:

            sock.settimeout(
                TCP_TIMEOUT
            )

            print(
                "TCP conectado."
            )

            print(
                "Local:",
                sock.getsockname(),
            )

            print(
                "Remoto:",
                sock.getpeername(),
            )

            # Firmware precisa de uma pequena pausa
            time.sleep(0.70)

            # ------------------------------------------------
            # 3. INFORMAÇÕES DO INSTRUMENTO
            # ------------------------------------------------

            info = get_instrument_info(
                sock
            )

            print(
                "\nInstrumento:",
                info.get(
                    "UnitIdentCode"
                ),
            )

            print(
                "Serial:",
                info.get(
                    "SerialNumber"
                ),
            )

            print(
                "Firmware:",
                info.get(
                    "FirmwareVersion"
                ),
            )

            # ------------------------------------------------
            # 4. BUSCA ÚLTIMA MEDIÇÃO
            # ------------------------------------------------

            measurement = (
                get_latest_measurement(
                    sock
                )
            )

            # ------------------------------------------------
            # 5. MOSTRA TABELA
            # ------------------------------------------------

            print_measurement(
                measurement
            )

            # ------------------------------------------------
            # 6. MOSTRA CADA DADO SEPARADAMENTE
            # ------------------------------------------------

            print_individual_values(
                measurement
            )

            # ------------------------------------------------
            # 7. EXEMPLOS DIRETOS DE USO
            # ------------------------------------------------

            print(
                "\n=== EXEMPLOS ==="
            )

            print(
                "Somente L* 15°:",
                get_L(
                    measurement,
                    15,
                ),
            )

            print(
                "Somente a* 25°:",
                get_a(
                    measurement,
                    25,
                ),
            )

            print(
                "Somente b* 105°:",
                get_b(
                    measurement,
                    105,
                ),
            )

            print(
                "LAB completo 45°:",
                get_lab(
                    measurement,
                    45,
                ),
            )

    finally:
        discovery.close()


if __name__ == "__main__":
    main()
