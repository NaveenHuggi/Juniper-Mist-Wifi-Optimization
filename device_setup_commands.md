# Juniper Device Setup Commands

This document contains a comprehensive list of all the CLI commands used to configure the Juniper SRX300 Firewall and EX2300 Switch for the network implementation.

---

## 1. Juniper SRX300 Firewall Configuration

The following command sets must be executed in configuration mode on the SRX300.

### Layer 3 Interface IP Assignment
Assign IP addresses to the physical interfaces to permit routing between the Untrust (WAN) and Trust (LAN) networks.
```bash
set interfaces ge-0/0/2 unit 0 family inet address 172.20.99.210/24
set interfaces ge-0/0/5 unit 0 family inet address 192.168.10.1/24
```

### Security Zone Assignment and Interface Binding
Map the configured interfaces to the appropriate security zones and permit required system services (like DHCP).
```bash
set security zones security-zone trust interfaces ge-0/0/5.0 host-inbound-traffic system-services dhcp
set security zones security-zone untrust interfaces ge-0/0/2.0
```

### DHCP Server and Address Pool Configuration
Enable automatic IP allocation, DNS assignment, and default gateway routing for LAN devices.
```bash
set system services dhcp pool 192.168.10.0/24 address-range low 192.168.10.10
set system services dhcp pool 192.168.10.0/24 address-range high 192.168.10.254
set system services dhcp pool 192.168.10.0/24 name-server 8.8.8.8
set system services dhcp pool 192.168.10.0/24 router 192.168.10.1
```

### Source NAT (SNAT) Configuration
Translate private internal IPs from the Trust zone to the public interface IP on the Untrust zone.
```bash
set security nat source rule-set trust-to-untrust from zone trust
set security nat source rule-set trust-to-untrust to zone untrust
set security nat source rule-set trust-to-untrust rule src-nat match source-address 0.0.0.0/0
set security nat source rule-set trust-to-untrust rule src-nat then source-nat interface
set security nat source rule-set trust-to-untrust rule source-nat-rule match source-address 0.0.0.0/0
set security nat source rule-set trust-to-untrust rule source-nat-rule then source-nat interface
```

### Security Policy Configuration
Define bidirectional traffic flow laws across the zones. The rules allow outbound access across the Trust and Untrust boundaries while blocking inbound initiation from the untrusted WAN.
```bash
# Allow local Trust zone objects out to Untrust
set security policies from-zone trust to-zone untrust policy allow-all match source-address any
set security policies from-zone trust to-zone untrust policy allow-all match destination-address any
set security policies from-zone trust to-zone untrust policy allow-all match application any
set security policies from-zone trust to-zone untrust policy allow-all then permit

set security policies from-zone trust to-zone untrust policy trust-to-untrust match source-address any
set security policies from-zone trust to-zone untrust policy trust-to-untrust match destination-address any
set security policies from-zone trust to-zone untrust policy trust-to-untrust match application any
set security policies from-zone trust to-zone untrust policy trust-to-untrust then permit

# Block Untrust traffic hitting the Trust zone
set security policies from-zone untrust to-zone trust policy block-all match source-address any
set security policies from-zone untrust to-zone trust policy block-all match destination-address any
set security policies from-zone untrust to-zone trust policy block-all match application any
set security policies from-zone untrust to-zone trust policy block-all then deny

# Permit intra-zone communication within the Trust perimeter
set security policies from-zone trust to-zone trust policy trust-to-trust match source-address any
set security policies from-zone trust to-zone trust policy trust-to-trust match destination-address any
set security policies from-zone trust to-zone trust policy trust-to-trust match application any
set security policies from-zone trust to-zone trust policy trust-to-trust then permit
```

### Default Static Route Configuration
Create an exit path to route data beyond local networks.
```bash
set routing-options static route 0.0.0.0/0 next-hop 172.20.99.1
```

---

## 2. Juniper EX2300 Switch Configuration

The following commands configure the Layer 2 access switch infrastructure to facilitate LAN traffic distribution.

### Access Port (Layer 2) Configuration
Set physical switch-ports as Ethernet Layer-2 Access mode mappings.
```bash
set interfaces ge-0/0/4 unit 0 family ethernet-switching interface-mode access
set interfaces ge-0/0/11 unit 0 family ethernet-switching interface-mode access
```

### Default Static Route Configuration (Management)
Set the switch forwarding route indicating the next hop gateway (pointing towards the firewall).
```bash
set routing-options static route 0.0.0.0/0 next-hop 192.168.1.1
```

---

## 3. Mist API Polling (Reference Only)

To interface with the Mist AI cloud and retrieve telemetry data covered in task 2, these REST API endpoints are utilized:

**Endpoint Base URL:** `https://api.mist.com`
**Authorization Header:** `Authorization: Token <MIST_API_TOKEN>`
**Content-Type:** `application/json`

```http
# Fetch Realtime Clients Info
GET /api/v1/sites/{site_id}/stats/clients

# Fetch Realtime Device Operation Specs
GET /api/v1/sites/{site_id}/stats/devices

# Extract AI Identified Network Anomalies
GET /api/v1/sites/{site_id}/insights/site/{site_id}/stats

# Retrieve AP Radio/Airwave Information
GET /api/v1/sites/{site_id}/stats/radios
```
