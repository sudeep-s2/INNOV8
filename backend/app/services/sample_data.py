from typing import List
from app.models.schemas import SampleDocument

SAMPLE_DOCUMENTS: List[SampleDocument] = [
    SampleDocument(
        id="sample_cyber_threat",
        title="NTRO Cyber Threat Advisory: APT-44 Exploitation of Power Grid SCADA Protocols",
        category="Cybersecurity & National Infrastructure",
        description="Detailed technical threat analysis on advanced persistent threats targeting regional power distribution telecontrol networks via zero-day vulnerabilities.",
        content="""NATIONAL TECHNICAL RESEARCH ORGANISATION (NTRO)
CYBER DEFENCE ADVISORY GROUP
CLASSIFICATION: SENSITIVE - FOR OFFICIAL USE ONLY
DATE: 2026-08-14
DOCUMENT ID: NTRO-CDAG-2026-089-R4

1. EXECUTIVE SUMMARY & THREAT OVERVIEW
Between June 12 and August 10, 2026, NTRO Telemetry and National Critical Information Infrastructure Protection Centre (NCIIPC) sensors detected persistent, multi-stage reconnaissance and lateral movement activities targeting 4 regional load dispatch centers (RLDCs) and 14 state-level electrical sub-transmission control nodes.

The adversary, tracked under cluster designation APT-44 (VORTEX PHANTOM), leveraged a previously unrecorded zero-day vulnerability in the IEC 60870-5-104 SCADA protocol gateway firmware (assigned CVE-2026-38910, CVSS score 9.8 Critical). 

Telemetry indicates that initial compromise occurred via spear-phishing campaigns delivering encrypted DLL side-loading payloads disguised as engineering grid maintenance schedules. To date, 3 sub-stations experienced intermittent telemetry drops of up to 47 seconds, though fail-safe mechanical interlocks prevented catastrophic grid desynchronization.

2. TECHNICAL FINDINGS & COMPROMISE METRICS
- Vulnerable Protocol: IEC 60870-5-104 (TCP Port 2404) and Modbus/TCP gateways manufactured by Apex Automation Systems (firmware versions 3.12 through 4.02).
- Blast Radius: 18 critical OT (Operational Technology) networks across Western and Northern Power Grids. 
- Data Exfiltration: 4.8 Gigabytes of proprietary single-line electrical diagrams, substation IP routing tables, and programmable logic controller (PLC) configuration binaries were transferred to external command-and-control (C2) servers hosted in bulletproof ASNs 49201 and 18392.
- Implant Characteristics: The malware payload ("GRIDSHADOW") resides purely in volatile memory (RAM), hooks kernel-level NDIS network drivers, and executes automated port knocking sequences every 3600 seconds to evade standard EDR signature heuristics.
- Exploit Reliability: 94% exploit execution success rate across legacy unsegmented Windows Server 2016 engineering workstations.

3. RISK & OPERATIONAL IMPACT ASSESSMENT
- Threat Severity: CRITICAL. If adversaries trigger synchronized trip-signals during peak load hours (18:00 - 22:00 IST), estimated grid imbalance could destabilize 12,500 Megawatts (MW) of transmission capacity, potentially affecting over 45 million citizens and commercial hubs across 3 states.
- Supply Chain Exposure: Over 32 private and state-owned power utilities utilize the affected Apex Automation gateway modules, with 68% lacking hardware-enforced unidirectional security gateways (data diodes).
- Persistence Threat: Memory-resident rootkits survived standard operating system reboots by patching UEFI bootloader NVRAM tables.

4. MANDATORY RECOMMENDED ACTIONS & REMEDIATION DIRECTIVES
Immediate Directives (Within 6 Hours):
1. Immediately isolate IEC-104 SCADA communication ports (TCP 2404) from all corporate IT networks and implement strict hardware data diodes.
2. Force emergency firmware update KB-2026-08-HOTFIX released by Apex Automation on August 12, 2026, or air-gap affected gateway controllers.
3. Terminate active outbound TCP connections to IP blocks 185.220.101.0/24 and 194.26.29.0/24.

Tactical & Strategic Directives (Within 72 Hours):
1. Deploy zero-trust OT microsegmentation across all SCADA human-machine interface (HMI) tiers.
2. Conduct forensic firmware integrity hashes across all substation RTUs (Remote Terminal Units).
3. Institute multi-factor cryptographic authentication for all engineering change commands exceeding 33kV switching thresholds.

5. IMPORTANT CAVEATS & SENSOR LIMITATIONS
- Passive sensor monitoring is currently blind to encrypted internal OT telemetry on legacy proprietary fieldbuses (RS-485 serial links).
- Threat actors may possess auxiliary dormant implants in redundant backup generators not yet queried during initial forensic sweeps.
"""
    ),
    SampleDocument(
        id="sample_quantum_initiative",
        title="National Quantum Mission: 2026-2030 Strategic Roadmap & Infrastructure Report",
        category="Strategic Technology & Deep Tech Policy",
        description="Comprehensive national strategy report covering quantum computing hardware scaling, post-quantum cryptography transition, and research funding allocations.",
        content="""NATIONAL MISSION ON QUANTUM TECHNOLOGIES & APPLICATIONS (NMQTA)
INTER-AGENCY STEERING COMMITTEE REPORT
REPORT NO: NMQTA-STRAT-2026-V2
PUBLISHED: JULY 2026

1. STRATEGIC CONTEXT AND OBJECTIVES
The Union Cabinet has sanctioned a revised budgetary outlay of INR 8,450 Crores ($1.02 Billion USD) for the National Quantum Mission spanning the fiscal cycle 2026-2030. The overarching mandate is to transition domestic quantum technologies from academic laboratory proofs-of-concept into resilient sovereign industrial and defense capabilities.

The core national benchmarks established for 2030 include:
1. Development of an indigenous 128 physical-qubit superconducting quantum processor with 99.7% 2-qubit gate fidelity.
2. Establishment of a 2,500-kilometer inter-city secure Quantum Key Distribution (QKD) satellite-terrestrial mesh network connecting 8 key strategic command headquarters.
3. Migration of 100% of national financial switches, defense communications, and critical intelligence archives to NIST-standardized Post-Quantum Cryptography (PQC) algorithms (Kyber-1024 and Dilithium-5).

2. KEY MILESTONES & PERFORMANCE METRICS
- Current Compute Baseline: In June 2026, the Centre for Development of Advanced Computing (C-DAC) and TIFR successfully benchmarked a 32-qubit transmon system operating at 15 milliKelvin dilution refrigerator conditions, achieving a 99.1% gate fidelity.
- Quantum Communication: Secure entanglement distribution demonstrated over a 450 km fiber testbed between New Delhi and Dehradun with a sustained secret key generation rate of 12.4 kbps and zero eavesdropping leakage.
- Human Capital Pipeline: 1,420 PhD candidates and specialized quantum systems engineers trained across 18 Indian Institutes of Technology (IITs) and IISc since 2024, exceeding the initial target by 28%.
- Budgetary Distribution: INR 3,100 Cr (36.7%) allocated to Hardware and Cryogenics Fabrication; INR 2,200 Cr (26%) for QKD and Quantum Internet; INR 1,850 Cr (21.9%) for Post-Quantum Migration; INR 1,300 Cr (15.4%) for Startups and Incubator Grants.

3. STRATEGIC RISKS & GEOPOLITICAL VULNERABILITIES
- Cryogenic Supply Chain Dependency: Over 92% of Helium-3 and dilution refrigeration hardware continues to be imported from only two supplier nations, creating severe single-point supply vulnerabilities in the event of export restrictions.
- Talent Retention: Domestic research institutions report an annual 34% talent flight of senior quantum researchers to private multinational tech corporations in North America and Western Europe.
- PQC Migration Latency: While defense nodes are on track for 2027 compliance, legacy banking core databases show an estimated 4-year migration lag, leaving financial transaction histories susceptible to "Harvest Now, Decrypt Later" adversary interception campaigns.

4. STRATEGIC RECOMMENDATIONS & DIRECTIVES
- Establish a National Cryogenics & Semiconductor Cleanroom Facility at Bangalore with dedicated Helium-3 recycling loops by Q4 2027.
- Enact the Sovereign Quantum Talent Fellowship, providing competitive remuneration and 5-year non-dilutive research seed capital up to INR 5 Crores per principal investigator.
- Mandate banking sector compliance with PQC hybrid TLS 1.3 key exchange by December 31, 2027 under RBI regulatory enforcement.
- Accelerate public-private co-development of quantum sensing prototypes for anti-submarine warfare (ASW) gravity gradiometry.
"""
    ),
    SampleDocument(
        id="sample_satellite_debris",
        title="Orbital Dynamics Bureau: Cosmos-2499 Debris Cascade Re-entry Incident Brief",
        category="Aerospace & Space Domain Awareness",
        description="Operational situational report regarding trackable space debris fragmentation, orbit decay telemetry, and atmospheric re-entry risk vectors.",
        content="""DIRECTORATE OF SPACE SITUATIONAL AWARENESS & TELEMETRY
INCIDENT SITUATION REPORT: ORBITAL DEBRIS RE-ENTRY (COSMOS-2499 FRAGMENTS)
REPORT CODE: SSA-INC-2026-7721
DATE OF ISSUANCE: AUGUST 28, 2026 | 04:30 UTC

1. INCIDENT BACKGROUND & SENSOR TELEMETRY
On August 26, 2026 at 18:14 UTC, high-resolution Multi-Object Tracking Radars (MOTR) detected a secondary hypervelocity collision event in low Earth orbit (altitude 512 km, inclination 82.5 degrees) involving cataloged space object NORAD ID 39765 (Cosmos-2499 fragment) and an untracked piece of micro-debris.

The collision resulted in catastrophic fragmentation, generating 347 trackable fragments larger than 5 centimeters in diameter and an estimated 12,000 untracked millimeter-sized particles.

Orbital trajectory modeling confirms that 3 large metallic fragments (designated OBJ-7721A, OBJ-7721B, and OBJ-7721C), with masses ranging from 45 kg to 110 kg, have entered rapid orbital decay with perigees dropping below 140 km.

2. QUANTITATIVE IMPACT & TRACKING METRICS
- Atmospheric Re-entry Window: August 30, 2026 between 14:15 UTC and 16:45 UTC (± 42 minutes uncertainty window).
- Trajectory Ground Track: The descending orbital path intersects coordinates extending across the Northern Indian Ocean, Southern Bay of Bengal, and adjacent coastal corridors (Latitude 8.2°N to 14.5°N, Longitude 76.0°E to 84.0°E).
- Estimated Mass Survivability: Thermodynamic ablation modeling indicates that the titanium fuel manifold and high-density tungsten counterweights of OBJ-7721A (approx. 38 kg intact mass) will likely survive atmospheric plasma burn-up and achieve ground/ocean impact at terminal velocities exceeding 280 km/h.
- Ground Impact Probability: Current mathematical modeling assesses a 91.4% probability of open oceanic splashdown and an 8.6% probability of coastal landfall impact within unpopulated maritime exclusion zones.

3. OPERATIONAL RISKS & MARITIME THREAT PROFILE
- Commercial Maritime Shipping: Dense shipping corridors across the southern shipping lanes (SLOCs) connecting the Malacca Strait experience an elevated localized kinetic hazard during the 150-minute re-entry window.
- Commercial Aviation: Civilian flight routes between Southeast Asia and Middle Eastern hubs traversing FIR Chennai require tactical altitude rerouting above FL380.

4. ACTION DIRECTIVES & INTER-AGENCY COORDINATION
- Directorate General of Shipping (DGS): Issue urgent NAVAREA VIII warning alerts instructing commercial vessels to maintain active radar watches and avoid designated precautionary zones between 13:00 and 18:00 UTC on August 30.
- Airports Authority of India (AAI): Implement temporary Notices to Airmen (NOTAMs) for air corridors W11, P628, and T4 during the projected atmospheric ingress timeframe.
- Coast Guard & Navy Search and Rescue (SAR): Pre-position oceanographic recovery cutters ICGS Samudra Prahari and INS Sandhayak for potential debris recovery and environmental telemetry verification.
"""
    )
]

def get_sample_documents() -> List[SampleDocument]:
    return SAMPLE_DOCUMENTS

def get_sample_by_id(doc_id: str) -> SampleDocument:
    for doc in SAMPLE_DOCUMENTS:
        if doc.id == doc_id:
            return doc
    return SAMPLE_DOCUMENTS[0]
