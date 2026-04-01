# Juniper Mist Setup & Configuration

This repository documents the setup and configuration process for a secure enterprise network utilizing **Juniper SRX** and **EX Series** devices, integrated with the **Juniper Mist AI** cloud platform for enhanced wireless connectivity and radio resource management.

## Project Overview

The core objective of this project is to establish a secure and intelligent network environment. The architecture is composed of:
- **Juniper SRX300 Firewall**: Acts as the gateway edge, providing routing, NAT, DHCP, and security policy enforcement between LAN (Trust) and WAN (Untrust) zones.
- **Juniper EX2300 Switch**: Facilitates Layer 2 access for end devices within the LAN.
- **Mist Access Points (AP32 & AP63)**: Deployed to deliver robust indoor and outdoor wireless coverage managed via the cloud.
- **Mist AI & Marvis**: Enables centralized monitoring, autonomous AI-level insights, and optimized wireless band steering.

## Architecture & Topology

The network relies on defining a strict security boundary using the SRX300 firewall. The configuration breaks down into two primary zones:
- **Trust Zone (Internal LAN)**: The trusted internal network (`192.168.10.0/24`). Devices here are served via a local DHCP pool.
- **Untrust Zone (WAN/Internet)**: The external connection to the ISP (`172.20.99.0/24`). Traffic from the Trust zone is NAT-ted to access external resources safely.

## Key Features Implemented

1. **Wired Network Foundation**:
   - Initialized the physical topology with Juniper SRX300 and EX2300.
   - Assigned static IPs for routing, configured a DHCP server on the firewall for dynamic LAN addressing, and mapped specific physical ports (`ge-0/0/2`, `ge-0/0/5`) to routing zones.
   - Designed Source NAT (SNAT) and zone-based security policies that allow internal clients outbound access while blocking inbound threats.
2. **Cloud-Managed Wireless Coverage**:
   - Onboarded Mist APs (AP32 and AP63) onto the Mist Dashboard.
   - Configured multiple wireless SSIDs (Corporate, Guest, IoT networks).
   - Applied **Mist AI Radio Resource Management (RRM)** for intelligent band steering between 2.4 GHz and 5 GHz, preventing congestion.
3. **API Integration & Validation (Telemetry)**:
   - Connected programmatically to Juniper Mist via secure APIs (using `<MIST_API_TOKEN>`).
   - Retrieved real-time access point statistics, wireless client connection data, RF metrics (noise floor, utilization), and **site-level AI insights** indicating anomalies like interference and capacity drops.

## Files in the Repository

- `device_setup_commands.md`: A comprehensive, copy-paste ready reference detailing all Junos OS CLI commands executed to configure the SRX300 firewall and EX2300 switch.

## Conclusion

This project highlights a modern, AI-driven networking approach where robust on-premise hardware seamlessly operates with a cloud-native intelligence layer. By leveraging Junos OS security and Mist APIs, the deployment successfully achieves high reliability, deep network visibility, and automated performance optimization.
