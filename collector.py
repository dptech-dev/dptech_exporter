import asyncio
import threading
import time
import traceback

from pysnmp.entity.engine import SnmpEngine
from pysnmp.hlapi.v3arch import UsmUserData, usmHMACMD5AuthProtocol, usmHMACSHAAuthProtocol, \
    usmDESPrivProtocol, usmAesCfb128Protocol, CommunityData, UdpTransportTarget, ContextData, get_cmd, bulk_cmd
from pysnmp.smi.rfc1902 import ObjectType, ObjectIdentity

from config import config_targets, Target
from metrics import *

debug: bool = False


def vb_float(vb, vfunc=None) -> float|None:
    if vb is None or isinstance(vb[1], NoSuchInstance) or isinstance(vb[1], Null): return None
    val = float(vb[1])
    if vfunc: val = vfunc(vb[1])
    return val
def vb_int(vb, vfunc=None) -> int|None:
    if vb is None or isinstance(vb[1], NoSuchInstance) or isinstance(vb[1], Null): return None
    val = int(vb[1])
    if vfunc: val = vfunc(vb[1])
    return val
def vb_str(vb, vfunc=None) -> str|None:
    if vb is None or isinstance(vb[1], NoSuchInstance) or isinstance(vb[1], Null): return None
    val = vb[1].prettyPrint()
    if vfunc: val = vfunc(vb[1])
    return val

def collector_start():
    for target in config_targets():
        threading.Thread(target=collector_thread, args=(target,), daemon=True).start()

class SnmpTarget:
    def __init__(self, target: Target):
        self.status = {}

        self.host = target.host
        self.target = target
        self.temp = target.snmp
        self.sysname = target.sysname if target.sysname else target.host
        self.maxRepetitions = 20

        self.model = None
        self.version = None
        self.sn = None

        temp = self.temp
        if temp.version == 'v3':
            if temp.priv_protocol:
                self.security_object = UsmUserData(
                    userName=temp.user,
                    authProtocol= usmHMACMD5AuthProtocol if temp.auth_protocol == 'md5' else usmHMACSHAAuthProtocol,
                    authKey=temp.auth_key,
                    privProtocol= usmDESPrivProtocol if temp.priv_protocol == 'des' else usmAesCfb128Protocol,
                    privKey=temp.priv_key)
            elif temp.auth_protocol:
                self.security_object = UsmUserData(
                    userName=temp.user,
                    authProtocol=usmHMACMD5AuthProtocol if temp.auth_protocol == 'md5' else usmHMACSHAAuthProtocol,
                    authKey=temp.auth_key)
            else:
                self.security_object = UsmUserData(userName=temp.user)
        else:
            self.security_object = CommunityData(temp.community, mpModel=1)

        self.transport = asyncio.run(UdpTransportTarget.create((target.host, 161), temp.timeout, temp.retry))

    async def async_get(self, *oids) -> tuple[ObjectType,...]:
        object_types = [ObjectType(ObjectIdentity(oid)) for oid in oids]
        errorIndication, errorStatus, errorIndex, varBinds = await get_cmd(SnmpEngine(),
                   self.security_object,
                   self.transport,
                   ContextData(),
                   *object_types)
        if errorIndication or errorStatus:
            raise Exception(f"SNMP GET error: {errorIndication or errorStatus}")
        return varBinds

    def get(self, *oids) -> tuple[ObjectType,...]:
        return asyncio.run(self.async_get(*oids))

    async def async_bulk(self, *oids) -> tuple[ObjectType,...]:
        object_types = [ObjectType(ObjectIdentity(oid)) for oid in oids]
        errorIndication, errorStatus, errorIndex, varBinds = await bulk_cmd(SnmpEngine(),
                   self.security_object,
                   self.transport,
                   ContextData(),
                   0, self.maxRepetitions,
                   *object_types)
        if errorIndication or errorStatus:
            raise Exception(f"SNMP GET error: {errorIndication or errorStatus}")
        return varBinds

    def bulk(self, *oids) -> tuple[ObjectType, ...]:
        return asyncio.run(self.async_bulk(*oids))

    def table(self, *oids) -> list[list[ObjectType]]:
        rlist = []
        sts = [{'oid':o.split('.'), 'end': False, 'last': ['0']} for o in oids]
        end = False
        while not end:
            vbs = self.bulk(*[".".join(st['oid']+st['last']) for st in sts])
            i = 0
            while not end and i < len(vbs):
                if i+len(sts) > len(vbs):
                    break
                slist = []
                for j,st in enumerate(sts):
                    vb = vbs[i+j]
                    oid = str(vb[0]).split('.')
                    if len(oid) < len(st['oid']) or oid[:len(st['oid'])] != st['oid']:
                        end = True
                        break
                    st['last'] = oid[len(st['oid']):]
                    slist.append(vb)
                if not end:
                    rlist.append(slist)
                    i += len(sts)
        return rlist

    def table_light(self, *oids) -> list[list[ObjectType]]:
        rlist = []
        sts = [{'oid':o.split('.'), 'end': False, 'last': ['0']} for o in oids]
        end = False
        while not end:
            vbs = self.bulk(*[".".join(st['oid']+st['last']) for st in sts])
            i = 0
            while not end and i < len(vbs):
                if i+len(sts) > len(vbs):
                    break
                slist = []
                for j,st in enumerate(sts):
                    vb = vbs[i+j]
                    oid = str(vb[0]).split('.')
                    if len(oid) < len(st['oid']) or oid[:len(st['oid'])] != st['oid']:
                        end = True
                        break
                    st['last'] = oid[len(st['oid']):]
                    slist.append(vb)
                if not end:
                    rlist.append(slist)
                    i += len(sts)
            break
        return rlist


def collector_thread(target):
    snmp_target = SnmpTarget(target)
    interval = 60
    nt = time.monotonic()
    while True:
        collector_work(snmp_target)
        nt += interval
        t = time.monotonic()
        while nt < t:
            nt += interval
        time.sleep(nt - t)

def collector_work(target: SnmpTarget):
    status = 1
    try:
        collector_work_system(target)
        collector_work_cards(target)
        collector_work_ifs(target)

        SNMP_LAST_GAUGE.labels(host=target.host, sysname=target.sysname, model=target.model).set(time.time())
    except Exception as e:
        status = 0
        print(f"target {target.host} Exception: {str(e)}")
        if debug:
            traceback.print_exc()
    SNMP_STATUS_GAUGE.labels(host=target.host, sysname=target.sysname, model=target.model).set(status)

def collector_work_system(target: SnmpTarget):
    vbs = target.get(
        '1.3.6.1.2.1.1.3.0',       # upTime     0
        '1.3.6.1.2.1.1.5.0', # sysname       1
        '1.3.6.1.4.1.31648.3.15.3.0', # cpu util      2
        '1.3.6.1.4.1.31648.3.15.4.0', # cpu temp      3
        '1.3.6.1.4.1.31648.3.15.5.0', # mem util      4
        '1.3.6.1.4.1.31648.3.15.8.0', # mb temp       5
        '1.3.6.1.4.1.31648.3.3.0',    # sw version    6
        '1.3.6.1.4.1.31648.3.14.0',    # sn            7
        '1.3.6.1.2.1.1.1.0', # descr 8
        '1.3.6.1.2.1.1.6.0', # location 9
        '1.3.6.1.2.1.1.4.0', # contact 10
    )
    target.sysname = target.target.sysname if target.target.sysname else str(vbs[1][1])

    target.maxRepetitions = 10
    rows = target.table_light('1.3.6.1.2.1.47.1.1.1.1.5', '1.3.6.1.2.1.47.1.1.1.1.7')
    for row in rows:
        if vb_int(row[0]) != 3:
            continue
        target.model = vb_str(row[1])
        break

    labels = {'host': target.host, 'sysname': target.sysname, 'model': target.model}
    metric_update(UPTIME_GAUGE, labels, vbs[0], lambda vb: float(vb[1])/100)
    metric_update(CPU_USAGE_GAUGE, labels, vbs[2])
    metric_update(CPU_TEMPERATURE_GAUGE, labels, vbs[3])
    metric_update(MEMORY_USAGE_GAUGE, labels, vbs[4])
    metric_update(MB_TEMPERATURE_GAUGE, labels, vbs[5])

    target.version = vb_str(vbs[6])
    target.sn = vb_str(vbs[7])
    sfunc = lambda vb: str(vb)
    SNMP_INFO_GAUGE.labels(host=target.host, sysname=target.sysname, model=target.model, version=target.version, sn=target.sn,
        descr=vb_str(vbs[8], sfunc), location=vb_str(vbs[9], sfunc), contact=vb_str(vbs[10], sfunc)).set(1)


def collector_work_cards(target: SnmpTarget):
    target.maxRepetitions = 20
    rows = target.table(
        '1.3.6.1.4.1.31648.6.1.1.3', # model
        '1.3.6.1.4.1.31648.6.1.1.6', # cpu util
        '1.3.6.1.4.1.31648.6.1.1.7',  # mem util
        '1.3.6.1.4.1.31648.6.1.1.12',  # lcpu util
        '1.3.6.1.4.1.31648.6.1.1.13',  # lmem util
        '1.3.6.1.4.1.31648.6.1.1.16', # cpu temp
        '1.3.6.1.4.1.31648.6.1.1.17'  # card temp
    )
    for row in rows:
        slot = str(row[0][0]).split('.')[11]
        card = str(row[0][1])
        labels = {'host': target.host, 'sysname': target.sysname, 'model': target.model, 'slot': slot, 'card': card}
        metric_update(CARD_CPU_USAGE_GAUGE, labels, row[1])
        metric_update(CARD_MEMORY_USAGE_GAUGE, labels, row[2])
        metric_update(CARD_LCPU_USAGE_GAUGE, labels, row[3])
        metric_update(CARD_LMEM_USAGE_GAUGE, labels, row[4])
        metric_update(CARD_CPU_TEMPERATURE_GAUGE, labels, row[5])
        metric_update(CARD_TEMPERATURE_GAUGE, labels, row[6])


def collector_work_ifs(target: SnmpTarget):
    st = target.status.get('snmp_if')
    if not st:
        st = {'last': 0.0}
        target.status['snmp_if'] = st
    pre = st['last']
    tm = time.monotonic()
    tl = tm - pre
    if tl + 0.1 < 300: return
    st['last'] = tm

    target.maxRepetitions = 10
    rows = target.table(
        '1.3.6.1.2.1.31.1.1.1.1', # ifname
        '1.3.6.1.2.1.2.2.1.2', # ifdescr
        '1.3.6.1.2.1.2.2.1.3',  # iftype
        '1.3.6.1.2.1.31.1.1.1.6',  # inOctets
        '1.3.6.1.2.1.31.1.1.1.10',  # outOctets
        '1.3.6.1.2.1.2.2.1.13', # inDiscards
        '1.3.6.1.2.1.2.2.1.14',  # inErrors
        '1.3.6.1.2.1.2.2.1.19',  # outDiscards
        '1.3.6.1.2.1.2.2.1.20',  # outErrors
        '1.3.6.1.2.1.31.1.1.1.15',  # speed
        '1.3.6.1.2.1.2.2.1.8',  # opStatus
    )
    for row in rows:
        ifindex = str(row[0][0]).split('.')[11]
        ifname = str(row[0][1])
        ifdescr = str(row[1][1].__bytes__(), 'utf-8')
        iftype = int(row[2][1])
        iftype = _if_types.get(iftype) if iftype in _if_types is not None else str(iftype)
        labels = {'host': target.host, 'sysname': target.sysname, 'model': target.model, 'ifname': ifname, 'ifdescr': ifdescr, 'iftype': iftype}
        speed = float(row[9][1])*1000_000 if row[9] and not isinstance(row[9][1], NoSuchInstance) or isinstance(row[9][1], Null) else 0.0
        status = 1 if vb_int(row[10]) == 1 else 0

        def if_per_second(st, tl, ifindex, name, vb, vfunc = None):
            if vb is None or isinstance(vb[1], NoSuchInstance) or isinstance(vb[1], Null): return None
            val = float(vb[1])
            if vfunc: val = vfunc(val)
            old = st.get(f'{ifindex}_{name}')
            st[f'{ifindex}_{name}'] = val
            v = (val - old) / tl if old is not None and val >= old else None
            st[f'{ifindex}_{name}_val'] = v
            return v

        metric_update_float(IF_IN_BITS_GAUGE, labels, if_per_second(st, tl, ifindex, 'in_octets', row[3], lambda v: v*8))
        metric_update_float(IF_OUT_BITS_GAUGE, labels, if_per_second(st, tl, ifindex, 'out_octets', row[4], lambda v: v*8))
        metric_update_float(IF_IN_DISCARDS_GAUGE, labels, if_per_second(st, tl, ifindex, 'in_discards', row[5]))
        metric_update_float(IF_IN_ERRORS_GAUGE, labels, if_per_second(st, tl, ifindex, 'in_errors', row[6]))
        metric_update_float(IF_OUT_DISCARDS_GAUGE, labels, if_per_second(st, tl, ifindex, 'out_discards', row[7]))
        metric_update_float(IF_OUT_ERRORS_GAUGE, labels, if_per_second(st, tl, ifindex, 'out_errors', row[8]))
        metric_update_float(IF_STATUS_GAUGE, labels, status)
        metric_update_float(IF_SPEED_GAUGE, labels, speed)
        metric_update(IF_IN_BYTES_GAUGE, labels, row[3])
        metric_update(IF_OUT_BYTES_GAUGE, labels, row[4])
        metric_update(IF_IN_DISCARDS_COUNT_GAUGE, labels, row[5])
        metric_update(IF_IN_ERRORS_COUNT_GAUGE, labels, row[6])
        metric_update(IF_OUT_DISCARDS_COUNT_GAUGE, labels, row[7])
        metric_update(IF_OUT_ERRORS_COUNT_GAUGE, labels, row[8])
        if pre != 0.0 and speed > 0:
            metric_update_float(IF_IN_USAGE_GAUGE, labels, st[f'{ifindex}_in_octets_val'] / speed * 100)
            metric_update_float(IF_OUT_USAGE_GAUGE, labels, st[f'{ifindex}_out_octets_val'] / speed * 100)


_if_types = {
    1: 'other',             2: 'regular1822',       3: 'hdh1822',           4: 'ddnX25',
    5: 'rfc877x25',         6: 'ethernetCsmacd',    7: 'iso88023Csmacd',    8: 'iso88024TokenBus',
    9: 'iso88025TokenRing', 10: 'iso88026Man',      11: 'starLan',          12: 'proteon10Mbit',
    13: 'proteon80Mbit',    14: 'hyperchannel',     15: 'fddi',             16: 'lapb',
    17: 'sdlc',             18: 'ds1',              19: 'e1',               20: 'basicISDN',
    21: 'primaryISDN',      22: 'propPointToPointSerial',   23: 'ppp',      24: 'softwareLoopback',
    25: 'eon',              26: 'ethernet3Mbit',    27: 'nsip',             28: 'slip',
    29: 'ultra',            30: 'ds3',              31: 'sip',              32: 'frameRelay',
    33: 'rs232',            34: 'para',             35: 'arcnet',           36: 'arcnetPlus',
    37: 'atm',              38: 'miox25',           39: 'sonet',            40: 'x25ple',
    41: 'iso88022llc',      42: 'localTalk',        43: 'smdsDxi',          44: 'frameRelayService',
    45: 'v35',              46: 'hssi',             47: 'hippi',            48: 'modem',
    49: 'aal5',             50: 'sonetPath',        51: 'sonetVT',          52: 'smdsIcip',
    53: 'propVirtual',      54: 'propMultiplexor',  55: 'ieee80212',        56: 'fibreChannel',
    57: 'hippiInterface',   58: 'frameRelayInterconnect',   59: 'aflane8023',   60: 'aflane8025',
    61: 'cctEmul',          62: 'fastEther',        63: 'isdn',             64: 'v11',
    65: 'v36',              66: 'g703at64k',        67: 'g703at2mb',        68: 'qllc',
    69: 'fastEtherFX',      70: 'channel',          71: 'ieee80211',        72: 'ibm370parChan',
    73: 'escon',            74: 'dlsw',             75: 'isdns',            76: 'isdnu',
    77: 'lapd',             78: 'ipSwitch',         79: 'rsrb',             80: 'atmLogical',
    81: 'ds0',              82: 'ds0Bundle',        83: 'bsc',              84: 'async',
    85: 'cnr',              86: 'iso88025Dtr',      87: 'eplrs',            88: 'arap',
    89: 'propCnls',         90: 'hostPad',          91: 'termPad',          92: 'frameRelayMPI',
    93: 'x213',             94: 'adsl',             95: 'radsl',            96: 'sdsl',
    97: 'vdsl',             98: 'iso88025CRFPInt',  99: 'myrinet',          100: 'voiceEM',
    101: 'voiceFXO',        102: 'voiceFXS',        103: 'voiceEncap',      104: 'voiceOverIp',
    105: 'atmDxi',          106: 'atmFuni',         107: 'atmIma',          108: 'pppMultilinkBundle',
    109: 'ipOverCdlc',      110: 'ipOverClaw',      111: 'stackToStack',    112: 'virtualIpAddress',
    113: 'mpc',             114: 'ipOverAtm',       115: 'iso88025Fiber',   116: 'tdlc',
    117: 'gigabitEthernet', 118: 'hdlc',            119: 'lapf',            120: 'v37',
    121: 'x25mlp',          122: 'x25huntGroup',    123: 'trasnpHdlc',      124: 'interleave',
    125: 'fast',            126: 'ip',              127: 'docsCableMaclayer',   128: 'docsCableDownstream',
    129: 'docsCableUpstream',   130: 'a12MppSwitch',    131: 'tunnel',      132: 'coffee',
    133: 'ces',             134: 'atmSubInterface', 135: 'l2vlan',          136: 'l3ipvlan',
    137: 'l3ipxvlan',       138: 'digitalPSUline',  139: 'mediaMailOverIp', 140: 'dtm',
    141: 'dcn',             142: 'ipForward',       143: 'msdsl',           144: 'ieee1394',
    145: 'if-gsn',          146: 'dvbRccMacLayer',  147: 'dvbRccDownstream',    148: 'dvbRccUpstream',
    149: 'atmVirtual',      150: 'mplsTunnel',      151: 'srp',             152: 'voiceOverAtm',
    153: 'voiceOverFrameRelay', 154: 'idsl',        155: 'compositeLink',   156: 'ss7SigLink',
    157: 'propWirelessP2P', 158: 'frForward',       159: 'rfc1483',         160: 'usb',
    161: 'ieee8023adLag',   162: 'bgppolicyaccounting', 163: 'frf16MfrBundle',  164: 'h323Gatekeeper',
    165: 'h323Proxy',       166: 'mpls',            167: 'mfSigLink',       168: 'hdsl2',
    169: 'shdsl',           170: 'ds1FDL',          171: 'pos',             172: 'dvbAsiIn',
    173: 'dvbAsiOut',       174: 'plc',             175: 'nfas',            176: 'tr008',
    177: 'gr303RDT',        178: 'gr303IDT',        179: 'isup',            180: 'propDocsWirelessMaclayer',
    181: 'propDocsWirelessDownstream',  182: 'propDocsWirelessUpstream',    183: 'hiperlan2',   184: 'propBWAp2Mp',
    185: 'sonetOverheadChannel',    186: 'digitalWrapperOverheadChannel',   187: 'aal2',    188: 'radioMAC',
    189: 'atmRadio',        190: 'imt',             191: 'mvl',             192: 'reachDSL',
    193: 'frDlciEndPt',     194: 'atmVciEndPt',     195: 'opticalChannel',  196: 'opticalTransport',
    197: 'propAtm',         198: 'voiceOverCable',  199: 'infiniband',      200: 'teLink',
    201: 'q2931',           202: 'virtualTg',       203: 'sipTg',           204: 'sipSig',
    205: 'docsCableUpstreamChannel',    206: 'econet',  207: 'pon155',      208: 'pon622',
    209: 'bridge',          210: 'linegroup',       211: 'voiceEMFGD',      212: 'voiceFGDEANA',
    213: 'voiceDID',        214: 'mpegTransport',   215: 'sixToFour',       216: 'gtp',
    217: 'pdnEtherLoop1',   218: 'pdnEtherLoop2',   219: 'opticalChannelGroup', 220: 'homepna',
    221: 'gfp',             222: 'ciscoISLvlan',    223: 'actelisMetaLOOP', 224: 'fcipLink',
    225: 'rpr',             226: 'qam',             227: 'lmp',             228: 'cblVectaStar',
    229: 'docsCableMCmtsDownstream',    230: 'adsl2',   231: 'macSecControlledIF',  232: 'macSecUncontrolledIF',
    233: 'aviciOpticalEther',   234: 'atmbond',     235: 'voiceFGDOS',      236: 'mocaVersion1',
    237: 'ieee80216WMAN',   238: 'adsl2plus',       239: 'dvbRcsMacLayer',  240: 'dvbTdm',
    241: 'dvbRcsTdma',      242: 'x86Laps',         243: 'wwanPP',          244: 'wwanPP2',
    245: 'voiceEBS',        246: 'ifPwType',        247: 'ilan',            248: 'pip',
    249: 'aluELP',          250: 'gpon',            251: 'vdsl2',           252: 'capwapDot11Profile',
    253: 'capwapDot11Bss',  254: 'capwapWtpVirtualRadio',   255: 'bits',    256: 'docsCableUpstreamRfPort',
    257: 'cableDownstreamRfPort',   258: 'vmwareVirtualNic',    259: 'ieee802154',  260: 'otnOdu',
    261: 'otnOtu',          262: 'ifVfiType',       263: 'g9981',           264: 'g9982',
    265: 'g9983',           266: 'aluEpon',         267: 'aluEponOnu',      268: 'aluEponPhysicalUni',
    269: 'aluEponLogicalLink',  270: 'aluGponOnu',  271: 'aluGponPhysicalUni',  272: 'vmwareNicTeam',
    277: 'docsOfdmDownstream',  278: 'docsOfdmaUpstream',   279: 'gfast',   280: 'sdci',
    281: 'xboxWireless',    282: 'fastdsl', 283: 'docsCableScte55d1FwdOob', 284: 'docsCableScte55d1RetOob',
    285: 'docsCableScte55d2DsOob',  286: 'docsCableScte55d2UsOob',  287: 'docsCableNdf',    288: 'docsCableNdr',
    289: 'ptm',             290: 'ghn'
}

