# Commercial Content Plan

This document is the separate follow-on plan for making the product feel more commercial in language, page content, and day-to-day presentation.

It builds on the UX/navigation cleanup already described in [nice_to_have_implementation_plan.md](/home/jsoltoski/greenblatt/nice_to_have_implementation_plan.md), but it is narrower and more content-focused.

## 1. Purpose

The app already looks more structured than the milestone-era scaffold, but too much page copy still sounds like:

- internal product notes
- developer scaffolding
- operator-facing diagnostics
- implementation commentary instead of customer-facing value

This plan is about fixing that without turning the product into empty marketing copy.

## 2. Current Problems To Address

### Content Problems

- several pages still explain the system from the builder’s point of view rather than the user’s point of view
- some copy uses words like `authenticated shell`, `public surface`, `provider diagnostics`, or `operator`
- some pages still expose admin or infrastructure language too early
- headings often describe page mechanics rather than the business outcome of the page

### UI Problems

- the top navbar is too tall
- the navbar staying fixed while scrolling wastes vertical space and competes with page content
- the chrome is heavier than it needs to be, especially on smaller laptop screens

## 3. Content Principles

Use these rules consistently across the app:

- lead with user benefit, not system structure
- explain what the page helps the user accomplish
- keep infrastructure, provider, and admin wording out of general-purpose pages
- reserve technical language for settings, support, and admin-oriented views
- use plain English and shorter sentences
- keep call-to-action labels direct: `Run screen`, `Start backtest`, `Save template`, `Open history`
- remove milestone, scaffolding, or internal roadmap language from production UI

## 4. Voice And Messaging Direction

The product should sound like a research platform for disciplined investors, not like a dev environment.

Preferred tone:

- clear
- confident
- practical
- research-first

Avoid:

- “this page introduces”
- “authenticated shell”
- “operator tooling”
- “provider diagnostics” on user-facing surfaces unless the page is specifically for data operations
- references to Django, staging, or internal stack details outside support settings

## 5. Page Priorities

### Tier 1: First Impression Pages

Rewrite first:

- landing page
- login page
- dashboard

Goal:

- a new user should understand the product in under 20 seconds
- the copy should describe outcomes, not architecture

### Tier 2: Primary Workflow Pages

Next:

- universes
- screens
- backtests
- templates
- history

Goal:

- each page should clearly explain what it is for, what to do next, and which settings matter right now

### Tier 3: Automation And Team Pages

Then:

- schedules
- alerts
- collaboration
- jobs

Goal:

- keep the value proposition business-facing
- move system details behind expandable help, status pills, or secondary text

### Tier 4: Technical Surfaces

Last:

- providers
- settings
- admin-adjacent links

Goal:

- keep them useful for operators
- stop them from leaking technical jargon into the rest of the app

## 6. Content Rewrite Rules By Pattern

### Hero And Intro Copy

Replace:

- architecture summaries
- implementation notes
- route-based explanations

With:

- what the user can do here
- what result they should expect
- a suggested next action

### Empty States

Every empty state should include:

- what is missing
- why it matters
- the next obvious action

### Help Text

Help text should:

- support the main action
- explain only the important decision
- avoid teaching the whole system

### Error And Status Copy

Status text should:

- explain what failed in plain language
- avoid backend-only terms unless they are actionable
- suggest a recovery path when possible

## 7. Navigation And Screen-Space Plan

### Navbar Changes

The navbar should be changed in this order:

1. reduce vertical padding and card weight
2. stop using a persistent sticky layout by default
3. remove non-essential admin/developer links from the primary navigation
4. keep navigation readable on mobile through wrapping, not giant chrome blocks

### Target Result

- top chrome feels present but lightweight
- the page content owns the screen, not the navigation
- mobile still works without introducing a complicated menu system too early

## 8. Commercial Polish Additions

Beyond copy cleanup, the app should gradually add stronger commercial cues:

- benefit-led headlines
- more polished empty states
- clearer social-proof or trust-style language around reliability and repeatability
- consistent language for saved work, research history, and reusable workflows
- fewer references to raw implementation details in public and first-run surfaces

## 9. Suggested Rollout Order

### Phase 1

- landing page
- login page
- dashboard
- navbar compaction

### Phase 2

- screens and backtests
- universes and templates
- empty-state cleanup

### Phase 3

- history, schedules, alerts, collaboration
- CTA and success-message pass

### Phase 4

- providers and settings copy split into user-facing versus operator-facing sections
- final terminology audit across the app

## 10. Exit Criteria

This plan is complete when:

- new users no longer see obvious development or scaffold wording on first-contact pages
- the navbar no longer dominates the viewport
- the app reads like a commercial research product
- operator or admin language appears only where it is genuinely needed
- mobile layout remains intact while using less vertical chrome
