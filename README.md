# AI Incident Root Cause Analyzer 🚀

Welcome to the **Root-Cause-Agent** repository!

This repository hosts a professional, competition-ready incident investigation console engineered for modern SRE and DevOps teams. Designed specifically for the Agentic Hackathon, this project demonstrates a highly capable AI-driven workflow that safely evaluates active incidents, determines root causes through evidence chains, and suggests idempotent remediation actions.

---

## 🌟 Why This Project?

Modern infrastructure is complex. When a SEV-1 incident strikes, SREs spend valuable minutes digging through logs, correlating metrics across disparate services, and manually checking deployment histories. 

**The Root Cause Analyzer changes this paradigm.**

Instead of manual hunting, our system deploys a swarm of specialized AI agents:
1. **Alert Intake Agent**: Triage and assess incoming alerts.
2. **Logs Intelligence Agent**: Parse and extract anomalies from distributed log streams.
3. **Metrics Analysis Agent**: Identify latency spikes, error rate climbs, and resource exhaustion.
4. **Distributed Trace Agent**: Follow requests across microservices.
5. **Deployment Analysis Agent**: Correlate failures with recent code rollouts.
6. **Correlation Engine & Root Cause Analysis Agents**: Synthesize findings into actionable evidence chains and assign confidence scores to hypotheses.

---

## 🎯 Key Features & Highlights

* **Explainable AI (XAI)**: We don't just output a guess. Every AI conclusion comes with a mapped evidence chain and a calculated confidence score, ensuring transparency for critical operational decisions.
* **Idempotent Remediation Engine**: AI shouldn't break production. Our platform uses an audit-driven approach to simulate recovery commands (like rolling back deployments) safely, recording every action in an immutable audit log.
* **Real-time WebSocket Updates**: A lively, responsive UI that pushes state changes immediately. No polling required.
* **Production-Oriented Architecture**: Built with lightweight boundaries (SQLite, native Python API) but designed for a direct upgrade path to PostgreSQL, Kafka, and OpenTelemetry for enterprise scale.
* **WCAG-Compliant Professional Interface**: A beautiful, minimalist "light mode" interface modeled after industry-standard tools like Grafana and Datadog, ensuring it feels instantly familiar to operations personnel.

---

## 📂 Project Structure

All the core project files, documentation, and source code are located in the [`agenti-hackathon`](./agenti-hackathon/) directory.

Inside the `agenti-hackathon` folder, you will find:
- **`backend/`**: The core API server, Multi-Agent workflow logic, and data store models.
- **`frontend/`**: The lightweight, accessible HTML/CSS/JS user interface.
- **`tests/`**: Edge-case and workflow validation suites.
- **`scripts/`**: Helpful deployment utilities.
- **`README.md`**: Complete setup instructions, screenshots, and detailed API documentation.

👉 **Navigate to the [agenti-hackathon README](./agenti-hackathon/README.md) for full details on how to run the project locally or via Docker.**

---

*Built with passion for the Agentic Hackathon. Empowering SREs with Agentic Intelligence.*
