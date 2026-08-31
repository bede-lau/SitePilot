Product Requirements Document (PRD): SitePilot
1. Executive Summary & Motives
1.1 Document Overview
This document specifies the product requirements for SitePilot, an agentic operating system for solar Engineering, Procurement, and Construction (EPC) contractors and developers. It defines the core problem space, existing foundations, new feature extensions, data integrations, and the 4-minute presentation flow for hackathon evaluation.

1.2 Problem Statement
In the commercial and residential solar installation industry, hardware costs have commoditized, but soft costs (estimating, manual procurement back-and-forth, engineering revisions, and compliance verification) account for 50% to 65% of project overhead.

Quotation Friction: Supplier quotes arrive as unstructured PDFs with disparate units, currencies, and incoterms.

Engineering Bottlenecks: When component pricing or availability shifts, manual recalculations of string configurations, inverter compatibility, and DC/AC ratios create severe project delays.

Regulatory Complexity: Calculating real return on investment requires navigating shifting national frameworks (such as Malaysia's 2026 Regulatory Period 4 tariffs and Solar ATAP schemes).  
DOCX

1.3 Project Motive & Positioning
SitePilot transforms a fragmented workflow into a closed-loop, multi-agent AI system. It moves from field observation to quotation ingestion, automated engineering feasibility verification, and instant Purchase Order (PO) dispatch, eliminating manual administrative and technical friction.

2. Existing Baseline vs. New Add-On Scope
2.1 Existing Product Baseline
Field Interface (Telegram Bot): Receives roof and solar site photos from field engineers.

Computer Vision Module: Detects and counts physical solar panels on the roof surface.

Central Database & Web Dashboard: Logs site records, panel quantities, and initial project entries.

Basic Communication: Triggers outbound Requests for Quotation (RFQs) to suppliers.

2.2 New Feature Add-Ons
Centralized Conversational Control Plane: A web dashboard chat interface enabling project managers to execute procurement, engineering, and financial commands via natural language.

Procurement & Quote Parsing Agent: Ingests unstructured vendor PDFs, parses line items, calculates normalized cost metrics (RM/Wp), and verifies BloombergNEF Tier 1 status.

Feasibility & Engineering Rule Agent: Performs deterministic electrical string checks, inverter compatibility tests, temperature derating adjustments, and DC/AC loading checks.

Automated BOS & Protection Spec Generator: Automatically outputs required balance-of-system electrical protections (fuses, isolators, cables, surge protection devices) based on system sizing.  
DOCX

Techno-Economic Financial Engine: Models real-world monthly bill savings and payback timelines using 2026 TNB RP4 utility rate blocks and Solar ATAP export schemes.  
DOCX

Credibility & Confidence Scoring System: Displays an automated confidence metric (capped at 90% to 94%). Do not frame results as AI-generated. 
DOCX

Voice-Enabled Field Dictation: Field voice transcription and voice interaction powered by ElevenLabs.

3. Specification Blueprint: Extraction & Scope Boundary
Based on the calculation engine specification, this section delineates the components to implement versus those to deliberately exclude to maintain product focus.  
DOCX

Spec Component	Action	Product Justification
String Sizing & MPPT Formulas (Sec 4.6 & 5.5)

  
DOCX

IMPLEMENT	
Core functionality for the Feasibility Agent to mathematically validate equipment compatibility.  
DOCX

Grid-Tie Inverter Sizing (Sec 5.4)

  
DOCX

IMPLEMENT	
Enforces the standard 1.2x to 1.5x DC:AC ratio for grid-tied solar systems.  
DOCX

Protection & Cable Checklist (Sec 8)

  
DOCX

IMPLEMENT	
Auto-generates practical balance-of-system engineering specs (cables, SPDs, fuses).  
DOCX

Malaysia 2026 Reference Tables (Sec 3.3, 12.1, 12.3)

  
DOCX

IMPLEMENT	
Grounds financial calculations in actual TNB RP4 tariffs and Solar ATAP SMP rates.  
DOCX

Confidence Scoring Model (Sec 9)

  
DOCX

IMPLEMENT	
Communicates reliability percentages to judges and enterprise users.  
DOCX

B2C Utility Bill Upload & OCR (Sec 1, 2.1)

  
DOCX

EXCLUDE	Dilutes the enterprise EPC focus; SitePilot's primary field trigger is the roof visual count.
Google Solar API (Sec 2.2, 11)

  
DOCX

EXCLUDE	
Low API coverage in Southeast Asia; replaced by computer-vision panel detection.  
DOCX

Off-Grid Appliance Survey Forms (Sec 2.4, 4.4)

  
DOCX

EXCLUDE	
Residential consumer questionnaire flow that adds unnecessary friction to an enterprise demo.  
DOCX

4. Detailed Feature Requirements
4.1 Procurement & Quote Parsing Agent
Input Capability: Accepts raw supplier quotation files (PDF, image, or structured text) dragged directly into the dashboard chat interface.

Extraction Fields:

Supplier Name

Module / Inverter Brand and Exact Model Name

Quantity and Unit Pricing (in MYR or USD)

Wattage Rating per Unit (Wp)

Warranty Period and Stated Lead Time

Normalization Engine:

Automatically calculates normalized cost per Watt-peak: Price per Watt= 
Rated Panel Wattage
Unit Price
​
 .

Converts multi-currency quotes to standard Ringgit Malaysia (RM/Wp).

Bankability Verification:

Checks extracted panel manufacturers against the BloombergNEF (BNEF) Tier 1 registry.

Flags unlisted or Tier 2 manufacturers with visual warning badges.

4.2 Feasibility & Engineering Verification Agent
Trigger Mechanism: Triggered whenever a project manager queries component compatibility or approves a parsed quote.

Deterministic String Configuration:

Computes maximum allowable panels in series with cold-temperature buffer: Series Max=⌊ 
V 
oc
​
 
V 
max_MPPT
​
 ×0.85
​
 ⌋.  
DOCX

Validates that total string voltage at maximum power (V 
mp string
​
 =Series×V 
mp
​
 ) falls inside the inverter's active MPPT voltage operating window.  
DOCX

Confirms string open-circuit voltage (V 
oc string
​
 =Series×V 
oc
​
 ) does not exceed the inverter absolute maximum input voltage (V 
max_DC
​
 ).  
DOCX

Calculates parallel string count: Parallel Strings=⌈ 
Series Count
Total Panels
​
 ⌉.  
DOCX

Confirms short-circuit current (Total I 
sc
​
 =Parallel Strings×I 
sc
​
 ) remains below inverter current limits.  
DOCX

Inverter DC:AC Sizing Validation:

Verifies that the system capacity matches a 1.2x to 1.5x DC:AC ratio relative to inverter AC output.  
DOCX

Temperature Derating:

Applies a fixed 0.85 thermal performance derating factor for ambient Malaysian operating temperatures.  
DOCX

4.3 Automated BOS & Protection Specification Generator
DC Protection Spec:

String DC Fuse: Sized at 1.25×I 
sc
​
  per string.  
DOCX

DC Isolator: Rated for system voltage + 20%.  
DOCX

DC Surge Protection Device (SPD): Type 2 rated, auto-assigned per combiner box.  
DOCX

Cable Sizing:

DC PV String Cable: Assigned as 4 mm 
2
  (standard for runs ≤15m, <20A).  
DOCX

AC Interconnection Cable: Auto-calculated based on inverter maximum continuous AC current.  
DOCX

Compliance Standards:

Formats output as an auto-generated installer handoff checklist referencing IEC 62548 and TNB interconnection guidelines.  
DOCX

4.4 Techno-Economic Financial Engine
Yield & Generation Modeling:

Applies location-based Peak Sun Hours (default: 4.3 to 4.5 PSH/day for Peninsular Malaysia).  
DOCX

Calculates daily and monthly generation: Monthly Generation (kWh)=Array Capacity (kWp)×PSH×Effective Efficiency×30.  
DOCX

Tariff Application (TNB RP4):

Applies standard residential/commercial tiered blocks (effective rate: ~RM 0.44 to 0.54/kWh).  
DOCX

Export Scheme (Solar ATAP):

Applies System Marginal Price (SMP) export compensation rate (~RM 0.18/kWh) with zero credit rollover.  
DOCX

Financial Outputs:

Monthly bill savings in Ringgit Malaysia (RM).  
DOCX

Simple payback period expressed as a conservative range (e.g., 8 to 12 years).  
DOCX

4.5 Confidence Scoring Model
Reliability Metrics:

Visual badge embedded in the final design summary.  
DOCX

85% to 88%: Field photo count + standard parameters.  
DOCX

90% to 94%: Field photo count + parsed vendor quote + validated string matching.  
DOCX

Hard Guardrail: Confidence scores must never display 100%, accompanied by the mandatory disclaimer: "AI-estimated, installer-confirmed".  
DOCX

4.6 Voice Field Agent
Functionality: Field voice dictation and audio status synthesis.

Capabilities: Enables engineers on site to dictate roof characteristics (e.g., obstructions, shading, roof type) directly into the mobile interface and receive concise spoken design confirmations.

5. Integrations & Data Sources
5.1 External Integrations
┌────────────────────────────────────────────────────────────────────────┐
│                        SitePilot External APIs                         │
├───────────────────────┬──────────────────────┬─────────────────────────┤
│ Integration           │ Role / Purpose       │ Data Exchange           │
├───────────────────────┼──────────────────────┼─────────────────────────┤
│ Telegram Bot API      │ Field user interface │ Photos In, POs Out      │
│ ElevenLabs API        │ Voice dictation      │ Speech-to-Text & Audio  │
│ Vision / OCR API      │ Supplier quote parse │ Unstructured PDF to JSON│
│ LLM Provider Engine   │ Multi-agent brain    │ Function / Tool Calling │
│ NREL SAM / CEC Tables │ Hardware parameters  │ Direct CSV / DataFrames │
└───────────────────────┴──────────────────────┴─────────────────────────┘
Telegram Bot API: Mobile gateway for field staff to send site photos and receive compiled purchase orders.

ElevenLabs API (Scribe v2 / Conversational AI): Ingests speech audio from field staff and returns natural audio status updates.

Vision & OCR API (e.g., GPT-4o Vision or AWS Textract): Parses unstructured tables, line items, and text from vendor PDF quotes.

LLM Reasoning Core (OpenAI / Anthropic / Gemini): Drives the conversational workspace and orchestrates tool calling across deterministic math functions.

5.2 Hardware Component Data Access
Primary Repository: NREL System Advisor Model (SAM) / California Energy Commission (CEC) Component Database.

Access Method: Programmatically queried locally via the pvlib Python library (pvlib.pvsystem.retrieve_sam('CECMod') and pvlib.pvsystem.retrieve_sam('CECInverter')) or direct ingestion of the open NREL GitHub CSV library.

Exact Data Repository URL: [https://github.com/NREL/SAM/tree/develop/deploy/libraries](https://github.com/NREL/SAM/tree/develop/deploy/libraries)

Fallback Strategy: If a newly released panel model is unlisted in the CEC database, the Quote Parsing Agent extracts V 
oc
​
 , I 
sc
​
 , and V 
mp
​
  directly from the uploaded manufacturer quotation datasheet.  
DOCX

6. End-to-End 4-Minute Hackathon Demo Script
Minute 0:00 to 1:00: Field Capture & Site Trigger
Visual: Mobile phone screen displaying the Telegram Bot interface.

Action: The presenter uploads a real rooftop photo.

Voice Agent: Presenter speaks a quick note: "Site has minimal shading, standard metal deck roof."

Result: Computer vision identifies panel layouts (e.g., 20 panels detected = 11 kWp potential array). The agent dispatches an automated RFQ to connected suppliers.

Minute 1:00 to 2:15: Unstructured Quote Ingestion (Dashboard)
Visual: Centralized web dashboard chat workspace.

Action: The presenter drags and drops a messy, multi-item supplier PDF quote into the chat.

Prompt: "Extract this quote, normalize the unit economics, and check manufacturer tier status."

Result: The Procurement Agent extracts line items: Longi Hi-MO7 550W panels at RM 467/unit (normalized to RM 0.85/Wp) and confirms BNEF Tier 1 status.  
DOCX

Minute 2:15 to 3:15: Automated Engineering & Feasibility Check
Visual: Dashboard chat with real-time technical calculation output.

Prompt: "Can we pair these panels with a standard 10kW Huawei string inverter?"

Action: The Feasibility Agent executes string formulas:

Verifies V 
oc cold
​
  (148.8V) remains well below the 500V limit.  
DOCX

Validates string V 
mp
​
  (124.5V) falls within the MPPT operating window.  
DOCX

Calculates DC:AC loading ratio at 1.1x to 1.3x.  
DOCX

Output: Displays approved string configuration (3S x 5P), an auto-generated BOS protection spec (4mm² PV cables, Type 2 DC SPD, 17.5A fuses), and a 92% Confidence Badge.  
DOCX

Minute 3:15 to 4:00: Financial Payback & PO Dispatch
Visual: Financial summary card and PDF generator.

Action: The Financial Engine computes energy yield under Malaysia TNB RP4 and Solar ATAP export rates, showing a 9.2-year payback.  
DOCX

Closing: Presenter clicks "Approve & Generate PO". The agent generates an installer-ready PO package and sends it directly back to the field engineer's Telegram thread.

7. Success Metrics & Judging Criteria Alignment
Technical Feasibility (25%): Leverages deterministic electrical formulas (Voc cold buffer, MPPT matching, IEC cable sizing) rather than relying on LLM approximations.  
DOCX

Commercial Viability (25%): Directly reduces EPC soft costs by collapsing days of quotation parsing and engineering revisions into seconds.

Industry Relevance (20%): Specifically customized for current Malaysian clean energy frameworks (TNB RP4 tariffs, Solar ATAP SMP rates, SEDA/ST standards).  
DOCX

Scalability (15%): Pure software architecture utilizing standard APIs, local tabular lookups, and minimal external database dependencies.

ESG / National Impact (15%): Accelerates national rooftop solar adoption by removing administrative and engineering barriers for solar contractors.