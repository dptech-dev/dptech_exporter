# DPtech-Exporter
Prometheus exporter for DPtech network device. This exporter only need to be installed on one server connected to the device, it will collect all the statistics on the device.

Visit http://localhost:9091/ to verify the exporter is running.

[Grafana dashboard example](https://grafana.com/grafana/dashboards/11111)

## Requirements

* python3
* prometheus-client (need to be installed with pip)
* pysnmp (need to be installed with pip)
* pysnmpcrypto (need to be installed with pip)
* pyyaml (need to be installed with pip)

## Usage
Metrics are exported on the chosen `HTTP` port. 

```
usage: dptech_exporter.py [-h] [--port PORT]
                              [--file INPUT_FILE]

Prometheus collector for DPtech device

optional arguments:
  -h, --help            show this help message and exit
  --port PORT           Http port, default is 9091
  --file INPUT_FILE
                        Configure file, default is /etc/dptech_exporter.yml
```

## Configuration
Save the network devices and access templates to be monitored. default: `/etc/dptech_exporter.yml`

```
# snmp access template define
snmp_templates:
  - name: default
    version: v2c
    community: public_default
#   timeout: 3
#   retry: 1
  - name: temp_v3
    version: v3
    user: user
    auth_protocol: md5
    auth_key: 12345678
    priv_protocol: des
    priv_key: 12345678

targets:
  - host: 192.168.0.1
    sysname: core           # use 'core' as sysname, default read by sysName(MIB)
#   snmp: default           # snmp access template, default is 'default'
  - host: 192.168.0.2
```

## Metrics

DPtech exporter metrics are prefixed with "dptech_".

### Global

Labels:
* `host`: host name or ip
* `sysname`: sysName from SNMP or manual set
* `model`: device model
* `version`: device software version (snmp_info)
* `sn`: device serial number (snmp_info)
* `descr`: device description (snmp_info)
* `location`: device location info (snmp_info)
* `contact`: device contact info (snmp_info)

Metrics:

| Name                           | Description                                                     |
|--------------------------------|-----------------------------------------------------------------|
| snmp\_info                     | The device info.                                                |
| snmp\_status                   | The snmp request status.                                        |
| snmp\_last\_time               | The last snmp request success time.                             |
| uptime\_seconds                | The running time of the device since its system initialization. |
| cpu\_usage\_percent            | Current CPU usage percentage.                                   |
| cpu\_temperature\_degree       | Current CPU temperature(°C).                                    |
| memory\_usage\_percent         | Current memory usage percentage.                                |
| mainboard\_temperature\_degree | Current Mainboard temperature(°C).                              |

### Card

Labels:
* `host`: host name or ip
* `sysname`: sysName from SNMP or manual set
* `model`: device model
* `slot`: slot number
* `card`: card model

Metrics:

| Name                           | Description                            |
|--------------------------------|----------------------------------------|
| card\_cpu\_usage\_percent      | CPU utilization percentage of card.    |
| card\_memory\_usage\_percent   | Percentage of memory used by the card. |
| card\_lcpu\_usage\_percent     | LCPU utilization percentage of card.   |
| card\_lmem\_usage\_percent     | Percentage of LMEM used by the card.   |
| card\_cpu\_temperature\_degree | CPU temperature of card (° C).         |
| card\_temperature\_degree      | Card temperature (° C).                |

### Interface

Labels:
* `host`: host name or ip
* `sysname`: sysName from SNMP or manual set
* `model`: device model
* `ifname`: interface name
* `ifdescr`: interface description
* `iftype`: interface type

Metrics:

| Name                    | Description                                                         |
|-------------------------|---------------------------------------------------------------------|
| if\_status              | Interface status.                                                   |
| if\_speed\_bps          | Interface speed.                                                    |
| if\_in\_bps             | Bits received by the interface per second.                          |
| if\_out\_bps            | Bits sent by the interface per second.                              |
| if\_in\_discards\_pps   | The number of packets discarded by the interface per second.        |
| if\_in\_errors\_pps     | Number of error packets received by the interface per second.       |
| if\_out\_discards\_pps  | Number of packets discarded to be sent by the interface per second. |
| if\_out\_errors\_pps    | Number of error packets to be sent by the interface per second.     |
| if\_in\_usage\_percent  | Interface inbound utilization.                                      |
| if\_out\_usage\_percent | Interface outbound utilization.                                     |
| if\_in\_bytes           | Bytes received by the interface.                                    |
| if\_out\_bytes          | Bytes sent by the interface.                                        |
| if\_in\_discards        | The number of packets discarded by the interface.                   |
| if\_in\_errors          | Number of error packets received by the interface.                  |
| if\_out\_discards       | Number of packets discarded to be sent by the interface.            |
| if\_out\_errors         | Number of error packets to be sent by the interface.                |

## Usecase

There are multiple ways to run the exporter.

### python3

Used in the system python environment or the python virtual environment.

```
pip install -r requirements.txt
python dptech_exporter.py -f dptech_exporter.yml
```

### uv

Used python uv.

```
uv sync
uv run dptech_exporter.py -f dptech_exporter.yml
```

### docker

Running with an uv container.

```
docker run -d --name dptech_exporter --restart unless-stopped \
    -p 9091:9091 \
    -v .:/app \
    -v ./dptech_exporter.yml:/etc/dptech_exporter.yml \
    -w /app \
    astral/uv:python3.12-bookworm-slim \
    uv run --link-mode=copy dptech_exporter.py
```

### docker compose (Recommend)

Running with an uv container by docker compose.

```
docker compose up -d
```
## Prometheus Configuration

Add the job to prometheus YAML file(prometheus.yml). example:

```
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'dptech-exporter'
    static_configs:
      - targets: ['localhost:9091']
```

## Grafana Dashboard

[ID 24399: DPtech Exporter Dashboard (Overview) ](https://grafana.com/grafana/dashboards/24399)

[ID 24400: DPtech Exporter Dashboard (Device) ](https://grafana.com/grafana/dashboards/24400)

## Licence

[MIT](LICENSE)

