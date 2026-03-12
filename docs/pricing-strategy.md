# Pricing Strategy Direction

## Goals
- Improve tenant revenue and conversion while protecting margin.
- Keep pricing explainable, auditable, and tenant-controlled.
- Enable AI-assisted recommendations without violating discount governance.

## Price Layers
- **Base price:** default sell price at product/variant scope.
- **Constraint layer:** min/max discount bounds and approval thresholds.
- **Context layer:** inventory age, sales velocity, margin profile, and campaign state.

## Guardrails
- Never produce pricing that violates tenant-configured bounds.
- Every sold line must persist effective price and discount reason context.
- AI suggestions are advisory unless explicitly approved by allowed roles/workflows.

## Optimization Signals
- Variant sell-through velocity
- Aging stock pressure
- Historical conversion by segment/channel
- Net margin after discounting
- Return-rate risk

## Implementation Phasing
1. Start with deterministic pricing policies and explicit constraints.
2. Add recommendation scoring using historical tenant data.
3. Introduce controlled experimentation with observability and rollback.
4. Keep all decisions traceable for audit and model improvement.
