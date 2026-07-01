# Enterprise Experience Showcase

**Author:** Shanmukha Raj  
**Date:** 1st July 2026

This document highlights relevant experiences from my career that demonstrate the skills and thinking required to build the Distributed Document Search Service described in the accompanying architecture document.

---

## 1. Distributed System: CineLite — Distributed ML Training Infrastructure

**Context:** As part of my Master's thesis project at San Jose State University, I designed and built CineLite — a distributed ML training system for text-to-video generation using custom diffusion models trained on 547GB of video datasets across 4 different architectures.

**Scale and Impact:**
- Trained models on **distributed A100/H200 GPU clusters** with 16M-1.7B parameter models
- Implemented **LoRA fine-tuning** reducing trainable parameters by 99% (16M vs 1.7B)
- Achieved **82% quality improvement** in generation quality (measured via CLIP scores and FVD metrics)
- Reduced **GPU training costs by 90%** through mixed precision training, gradient checkpointing, and efficient parameter-efficient fine-tuning
- Built **MLflow-based observability** for tracking hundreds of training runs across distributed infrastructure

**Distributed Systems Challenges Solved:**
The training system had to coordinate gradients across multiple GPU nodes efficiently. I used PyTorch FSDP (Fully Sharded Data Parallel) for model sharding across GPUs, with careful attention to communication overhead vs computation. Handling straggler GPU nodes required implementing timeout and re-schedule logic, similar to how our proposed document search service handles slow Elasticsearch replicas. I also implemented gradient accumulation to work around memory constraints, mirroring how we handle backpressure in queue-based systems.

**Relevance to Document Search:** The distributed coordination patterns, observability requirements, and cost-optimization mindset used in CineLite directly translate to designing the document search service — both require efficient distributed processing, careful monitoring, and cost-conscious architecture.

---

## 2. Performance Optimization: VeraAI ML Inference Infrastructure

**Context:** At VeraAI Technologies, our production ML model serving infrastructure was experiencing high inference latency (over 300ms p95) which was hurting user experience and violating our SLA commitments to enterprise customers. The system used SpatialLM perception models deployed via FastAPI microservices, with millions of inference requests per day.

**The Optimization:**
I led a comprehensive performance optimization effort focused on three areas:

1. **TensorRT Model Quantization:** Converted FP32 models to FP16 and INT8 formats, reducing model memory footprint by 60% and enabling faster GPU inference. Carefully calibrated INT8 quantization to maintain 95%+ detection accuracy while achieving 3x throughput improvement.

2. **CUDA Kernel Optimization:** Profiled the inference pipeline using NSight and identified bottlenecks in the preprocessing pipeline. Rewrote critical hot-path operations using fused CUDA kernels, eliminating unnecessary memory transfers between host and device.

3. **Dynamic Batching:** Implemented request batching at the model server level, grouping incoming requests within a 10ms window to maximize GPU utilization. Combined with priority queuing for latency-sensitive requests.

**Measurable Results:**
- **40% reduction in p95 inference latency** (from 300ms to 180ms)
- **95% detection accuracy maintained** despite aggressive quantization
- **99.2% uptime achieved** under peak load
- **Sub-200ms inference latency** across distributed microservices
- **3x throughput improvement** allowing us to serve more customers per GPU

**Trade-offs Made:**
The optimization required careful trade-off analysis. INT8 quantization introduced slight accuracy degradation which I validated extensively via A/B testing before rollout. Dynamic batching added complexity but was worth the throughput gain. These trade-off frameworks directly parallel the caching TTL decisions and eventual consistency choices in the document search service.

---

## 3. Production Incident: Real-Time ETL Pipeline Failures at VeraAI

**Context:** Our real-time ETL pipeline processing 500GB+ monthly data began experiencing intermittent failures, dropping approximately 15% of events. This was affecting downstream ML training data quality and customer analytics dashboards were showing stale data. The incident escalated when a major enterprise customer noticed missing analytics for a full 24-hour period.

**Incident Response:**
I led the incident response and root cause investigation:

**Detection:** Our monitoring dashboards flagged elevated error rates on the event message queue. Alert fired via PagerDuty within 5 minutes of the pattern emerging.

**Diagnosis:** Traced the issue through distributed logs (correlation IDs saved us here). The root cause was transient network failures between the message queue and downstream S3 writes, combined with insufficient retry logic. Under peak load, when S3 experienced brief slowdowns, our workers would fail after the first attempt and drop messages entirely.

**Mitigation:**
1. **Immediate fix:** Deployed a hotfix with exponential backoff retry logic (1s, 2s, 4s, 8s) with a maximum of 3 retries per message
2. **Message durability:** Enabled message persistence and added a Dead Letter Queue (DLQ) for messages that failed after max retries
3. **Reprocessing:** Wrote a recovery job to replay the DLQ once S3 was stable, recovering 12% of the 15% lost messages
4. **Long-term:** Implemented circuit breakers on downstream calls, added S3 request pooling with connection reuse, and improved observability with distributed tracing

**Measurable Results:**
- **Reduced pipeline failures by 40%** post-incident (from 15% to <2%)
- **Zero data loss** in subsequent similar incidents
- **95% of failed messages recovered** from DLQ during future incidents
- **Mean Time to Detection (MTTD) improved to under 3 minutes** with new monitoring

**Lessons Learned:**
Distributed systems will experience partial failures. Design for them from day one with retries, DLQs, and observability. These same patterns are core to the document search service design — the message queue with retry logic, DLQ handling, and circuit breakers directly reflect lessons learned from this incident.

---

## 4. Architectural Decision: Multi-Tenant AI Platform at SPM Technology

**Context:** At SPM Technology, we needed to onboard multiple enterprise clients with different requirements for ML models, data pipelines, and integrations. Each new client was taking 2-3 weeks of engineering work to spin up their infrastructure — this wasn't scalable as we planned to grow to 20+ clients within 6 months.

**Competing Concerns:**
The team debated three approaches:

1. **Dedicated Infrastructure per Client:** Complete isolation but expensive and slow to onboard (2-3 weeks each)
2. **Shared Infrastructure with Multi-Tenancy:** Fast onboarding but risk of cross-tenant data leaks and noisy neighbor issues
3. **Hybrid Approach:** Shared platform template + client-specific configuration

**The Architectural Decision:**
I proposed and implemented the **hybrid approach** — a reusable, multi-client isolated AI platform template orchestrated by Cloud Composer (Airflow DAGs) on GCP. Key design choices:

**Isolation Strategy:**
- Each client got their own GCP project with IAM boundaries (strong isolation)
- Airflow DAGs were parameterized templates deployed per client
- Shared code libraries with client-specific configuration files
- BigQuery datasets partitioned by client_id with row-level security

**Trade-offs Made:**
- **Chose configuration over code duplication** — one template serving all clients means bug fixes and features roll out to everyone
- **Chose stronger isolation over cost efficiency** — separate GCP projects cost more than shared but eliminate cross-tenant risk
- **Chose async orchestration over synchronous** — Airflow's async model made onboarding faster but requires careful state management

**Measurable Results:**
- **Client onboarding reduced from weeks of engineering to a configuration change** (typically 1-2 days)
- **Directly improved developer productivity** — engineers could focus on features instead of client-specific plumbing
- **Zero cross-tenant data incidents** to date
- **Enabled the team to scale to multiple new clients** without proportional headcount increase

**Relevance to Document Search:**
The multi-tenancy approach in this document search service is directly informed by this experience. The proposed hybrid model (shared code + per-tenant Elasticsearch indices + PostgreSQL Row-Level Security) balances the same concerns — strong isolation for security vs cost efficiency for scale. The trade-off documentation approach comes from having to justify similar decisions to stakeholders at SPM.

---

## AI Tool Usage Note

I used AI tools (Claude, ChatGPT) during the design of this document search service to:
- Brainstorm alternative architectural patterns
- Sanity-check trade-off analysis
- Draft initial versions of documentation for refinement
- Generate boilerplate code for the prototype

All final architectural decisions and reasoning are my own, informed by hands-on experience building the systems described above.

---

**Document End**