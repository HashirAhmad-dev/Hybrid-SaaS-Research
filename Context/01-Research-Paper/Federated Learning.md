# Federated Learning (future work, not built)

> Nothing on this page was implemented or evaluated. It is an architectural vision only and is not a contribution of the paper.

Centralizing raw API logs from legally separate organizations violates data sovereignty requirements. A future version could use a federated learning module.

- Each tenant trains a local LSTM on its own API telemetry and computes a weight update.
- **Differential privacy noise** is added to clipped gradients before leaving the tenant.
- A central coordinator aggregates updates with Federated Averaging (FedAvg).
- The aggregated model is broadcast back to all participants.

## Benefits
- Collective immunization: an attack pattern in one tenant hardens models for all.
- Softens the cold-start problem for new tenants.
- Raw logs never cross tenant boundaries.
