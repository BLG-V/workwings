# WorkWings Landing Redesign Spec

## Goal

Reposition the current landing page from the original AgentFlow branding to WorkWings, while keeping the existing frontend project as the implementation base.

## Audience

Engineering and product teams that need multi-agent delivery workflows with approvals, persisted artifacts, audit events, and controlled backend orchestration.

## Page Sections

- Header with WorkWings brand, product capability anchors, terms link, and login CTA.
- Hero explaining controlled multi-agent workflow delivery.
- Product proof panel showing a WorkWings run stream with paused approval state.
- Capability tabs for orchestration, approval, artifacts, and event streaming.
- Core module grid for project workflow, multimodal analysis, requirement baseline, prototype generation, approval recovery, and artifact persistence.
- Combined technology stack for AgentFlow frontend plus WorkWings backend.
- Scenario, control boundary, execution steps, CTA, and footer sections.

## Implementation Rules

- Preserve the current React, Vite, Tailwind, Radix UI, Framer Motion, and lucide-react stack.
- Do not modify the original WorkWings repository.
- Avoid hidden chain-of-thought UI. Show model messages, command summaries, workflow events, approvals, and artifacts instead.
- Do not expose secrets in frontend copy or mock data.
- Keep motion restrained and respect reduced-motion preferences.

## Success Criteria

- No legacy Chinese product naming or old kernel branding remains on the landing page or shared brand logo.
- WorkWings workflow kernel, approval flow, artifact persistence, SSE event stream, and combined stack are clearly described.
- Landing page builds successfully with the existing project tooling.
