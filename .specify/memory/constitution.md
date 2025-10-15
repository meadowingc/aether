<!--
Sync Impact Report:
- Version change: Initial → 1.0.0
- Added principles: Resource Efficiency, Simplicity & Clean UX, Privacy & Security, Cross-Platform Integration, Performance Constraints
- Added sections: Technology Standards, Resource Constraints
- Templates requiring updates: 
  ✅ Updated: plan-template.md constitution check section aligned
  ✅ Updated: spec-template.md scope requirements aligned
  ✅ Updated: tasks-template.md task categorization aligned
- Follow-up TODOs: None - all placeholders filled
-->

# Aether Constitution

## Core Principles

### I. Resource Efficiency (NON-NEGOTIABLE)
Aether MUST operate within minimal resource constraints due to shared VM hosting. All features must be designed with memory and CPU efficiency as primary concerns. Database queries must be optimized, caching strategies implemented where beneficial.

**Rationale**: Operating in a resource-constrained environment with other projects requires discipline in resource management to ensure stability and cost-effectiveness.

### II. Simplicity & Clean UX
The user experience must remain clean and minimal. Features should follow the principle of progressive disclosure - essential functionality is immediately accessible, advanced features are discoverable but not intrusive. The ephemeral nature of posts (disappearing from home page) is core to the user experience and must be preserved. UI complexity must be justified by user value.

**Rationale**: The project's appeal lies in its simplicity compared to complex social media platforms. This differentiates Aether from feature-heavy alternatives.

### III. Privacy & Security
User privacy is paramount. Personal data collection must be minimized, optional features must default to privacy-first settings, and all user data must be handled securely. Authentication mechanisms must be robust (2FA support), and cross-posting features must respect user consent and platform policies.

**Rationale**: Trust is essential for a social platform, especially for a hobby project with real users who rely on the service.

### IV. Cross-Platform Integration
Cross-posting capabilities (Mastodon, Bluesky/ATProto) are core features that must be maintained and expanded thoughtfully. API integrations must be resilient to external service changes, include proper error handling, and respect rate limits. New platform integrations must follow established patterns.

**Rationale**: Cross-posting functionality increases user engagement and provides value beyond simple status posting.

## Technology Standards

Django framework remains the core technology with Python 3.12+ requirement. Package management via `uv` for faster dependency resolution and installation. Database migrations must be backwards-compatible where possible. All new dependencies must be evaluated for resource impact and maintenance burden.

CSS frameworks and JavaScript libraries should be minimal and serve specific purposes. The current approach of custom CSS with minimal external dependencies should be maintained unless significant benefits justify additional complexity.

## Resource Constraints

Memory usage must be monitored and optimized. Database query efficiency is mandatory - N+1 query problems must be identified and resolved. Static file serving should leverage Caddy and Cloudflare CDN capabilities. Background tasks should be lightweight and efficient.

All new features must include resource impact assessment. Performance testing should be conducted in development environments that mirror production constraints as closely as possible.

## Governance

This constitution supersedes all other development practices and decisions. All feature specifications and implementation plans must verify compliance with these principles before development begins.

Version changes follow semantic versioning: MAJOR for principle changes, MINOR for new principles/constraints, PATCH for clarifications. All amendments require documentation of impact and migration planning.

Complexity must always be justified against user value and resource constraints. When in doubt, choose the simpler implementation that meets user needs while respecting resource limitations.

**Version**: 1.0.0 | **Ratified**: 2025-10-15 | **Last Amended**: 2025-10-15
