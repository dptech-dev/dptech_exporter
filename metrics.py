from prometheus_client import *
from pysnmp.proto.rfc1902 import Null
from pysnmp.proto.rfc1905 import NoSuchInstance

# system
system_labels = ['host', 'sysname', 'model']
SNMP_INFO_GAUGE = Gauge('dptech_snmp_info', 'The device info', ['host', 'sysname', 'model', 'version', 'sn', 'descr', 'location', 'contact'])
SNMP_STATUS_GAUGE = Gauge('dptech_snmp_status', 'The snmp request status', system_labels)
SNMP_LAST_GAUGE = Gauge('dptech_snmp_last_time', 'The last snmp request success time', system_labels)
UPTIME_GAUGE = Gauge('dptech_uptime_seconds', 'The running time of the device since its system initialization', system_labels)
CPU_USAGE_GAUGE = Gauge('dptech_cpu_usage_percent', 'Current CPU usage percentage', system_labels)
CPU_TEMPERATURE_GAUGE = Gauge('dptech_cpu_temperature_degree', 'Current CPU temperature(°C)', system_labels)
MEMORY_USAGE_GAUGE = Gauge('dptech_memory_usage_percent', 'Current memory usage percentage', system_labels)
MB_TEMPERATURE_GAUGE = Gauge('dptech_mainboard_temperature_degree', 'Current Mainboard temperature(°C)', system_labels)

# card
card_labels = ['host', 'sysname', 'model', 'slot', 'card']
CARD_CPU_USAGE_GAUGE = Gauge('dptech_card_cpu_usage_percent', 'CPU utilization percentage of card', card_labels)
CARD_MEMORY_USAGE_GAUGE = Gauge('dptech_card_memory_usage_percent', 'Percentage of memory used by the card', card_labels)
CARD_LCPU_USAGE_GAUGE = Gauge('dptech_card_lcpu_usage_percent', 'LCPU utilization percentage of card', card_labels)
CARD_LMEM_USAGE_GAUGE = Gauge('dptech_card_lmem_usage_percent', 'Percentage of LMEM used by the card', card_labels)
CARD_CPU_TEMPERATURE_GAUGE = Gauge('dptech_card_cpu_temperature_degree', 'CPU temperature of card (° C)', card_labels)
CARD_TEMPERATURE_GAUGE = Gauge('dptech_card_temperature_degree', 'Card temperature (° C)', card_labels)

# interface
if_labels = ['host', 'sysname', 'model', 'ifname', 'ifdescr', 'iftype']
IF_STATUS_GAUGE = Gauge('dptech_if_status', 'Interface status', if_labels)
IF_SPEED_GAUGE = Gauge('dptech_if_speed_bps', 'Interface speed', if_labels)
IF_IN_BITS_GAUGE = Gauge('dptech_if_in_bps', 'Bits received by the interface per second', if_labels)
IF_OUT_BITS_GAUGE = Gauge('dptech_if_out_bps', 'Bits sent by the interface per second', if_labels)
IF_IN_DISCARDS_GAUGE = Gauge('dptech_if_in_discards_pps', 'The number of packets discarded by the interface per second', if_labels)
IF_IN_ERRORS_GAUGE = Gauge('dptech_if_in_errors_pps', 'Number of error packets received by the interface per second', if_labels)
IF_OUT_DISCARDS_GAUGE = Gauge('dptech_if_out_discards_pps', 'Number of packets discarded to be sent by the interface per second', if_labels)
IF_OUT_ERRORS_GAUGE = Gauge('dptech_if_out_errors_pps', 'Number of error packets to be sent by the interface per second', if_labels)
IF_IN_USAGE_GAUGE = Gauge('dptech_if_in_usage_percent', 'Interface inbound utilization', if_labels)
IF_OUT_USAGE_GAUGE = Gauge('dptech_if_out_usage_percent', 'Interface outbound utilization', if_labels)
IF_IN_BYTES_GAUGE = Gauge('dptech_if_in_bytes', 'Bytes received by the interface', if_labels)
IF_OUT_BYTES_GAUGE = Gauge('dptech_if_out_bytes', 'Bytes sent by the interface', if_labels)
IF_IN_DISCARDS_COUNT_GAUGE = Gauge('dptech_if_in_discards', 'The number of packets discarded by the interface', if_labels)
IF_IN_ERRORS_COUNT_GAUGE = Gauge('dptech_if_in_errors', 'Number of error packets received by the interface', if_labels)
IF_OUT_DISCARDS_COUNT_GAUGE = Gauge('dptech_if_out_discards', 'Number of packets discarded to be sent by the interface', if_labels)
IF_OUT_ERRORS_COUNT_GAUGE = Gauge('dptech_if_out_errors', 'Number of error packets to be sent by the interface', if_labels)

def metric_update(metric: Gauge, labels: dict, vb, vfunc = None):
    if vb is None or isinstance(vb[1], NoSuchInstance) or isinstance(vb[1], Null):
        return
    val = vfunc(vb) if vfunc else float(vb[1])
    metric.labels(**labels).set(val)

def metric_update_float(metric: Gauge, labels: dict, val, vfunc = None):
    if vfunc: val = vfunc(val)
    if val is None: return
    metric.labels(**labels).set(val)