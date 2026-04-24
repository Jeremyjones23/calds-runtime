# CalDS 10-Minute Plan of Action Brief

## What Problem We Are Solving

CalDS is being built to solve a very specific problem: public-interest oversight work is slow, fragmented, and hard to defend when the source material is spread across filings, grant records, audit findings, spending data, and entity relationships. The current process often forces a human operator to spend days collecting, sorting, and cross-checking records before they can even decide whether a lead deserves deeper review.

The opportunity is not to replace judgment. The opportunity is to compress that early-stage triage into something much faster, more structured, and more defensible. CalDS should help a reviewer move from a pile of disconnected records to a ranked set of source-cited leads, with uncertainty and missing data stated plainly. That is the real wedge.

## What We Have Already Designed

The good news is that a large part of the conceptual work is already done. We have already defined the product posture, which is evidence-first lead generation rather than accusation generation. We have already separated the future system into truth, search, workflow, and agent layers. We have already designed a bounded agent team so that case direction, retrieval planning, evidence analysis, scoring, and sentinel review are distinct responsibilities rather than one giant model improvising everything.

We have also already done the business-side framing. The product is not being positioned as software that proves corruption. It is being positioned as software that compresses audit and investigation triage into evidence-backed, reviewer-safe leads. That is the right framing for credibility, safety, and eventual government sale.

## The Architecture Decision In Plain English

The main unresolved question was what harness should run the agents. After reviewing the current options critically, the answer is that CalDS should use a workflow-first stack, not an agent-first runtime.

In plain English, that means one layer should keep long-running jobs alive even when systems fail, one layer should coordinate the specialist agents inside a case, and one layer should handle model calls, handoffs, and tracing. The recommendation is to let Temporal handle durable workflow execution, LangGraph handle bounded agent orchestration, and a provider SDK layer handle model-facing tool calls, handoffs, and tracing.

That division is not academic. It is what keeps a politically sensitive system from turning into a black box. If one runtime tries to be the database, the scheduler, the memory layer, the approval system, and the agent brain all at once, you lose clarity very quickly. CalDS should avoid that trap from the beginning.

## Why We Are Not Making Hermes The Core Harness Right Now

Hermes is a legitimate option and it has real strengths. It offers a strong operator experience, flexible model routing, persistent memory, and a rich skill system. If the goal were to create an internal research copilot or a persistent founder assistant, it would be a strong candidate.

But that is not the exact problem CalDS has to solve. CalDS needs explicit durability, clean workflow resumption, bounded specialist coordination, strong isolation between delegated workstreams, and reviewer-safe controls. Public Hermes materials and issue discussions suggest that its current delegation model still carries some limitations that matter here, including in-process delegated children, concerns about terminal-backend isolation, and synchronous delegation that can block a coordinator pattern.

That does not make Hermes bad. It makes it a better fit for experimentation, internal acceleration, and inspiration than for being the core runtime of a production oversight stack.

## What We Should Build First

The first build should be narrow and disciplined. We should not try to launch a giant autonomous system. We should stand up one complete end-to-end case workflow that proves the architecture works under pressure.

That first workflow should do five things well. It should open a bounded case. It should retrieve evidence across a small but high-signal corpus. It should assemble an evidence bundle with provenance. It should produce a reviewer-safe lead candidate. And it should pause for explicit human review before anything stronger is said or done.

If that path is durable, traceable, and understandable, the rest of the system can be added incrementally. If that path is not stable, scaling agent count or data breadth will only multiply confusion.

## What Decisions Still Need Executive Buy-In

There are a few decisions that still need explicit agreement.

First, the team needs to commit to a reliability-first architecture even though it is less flashy than a single-agent runtime. Second, the team needs to accept that CalDS is a governed workflow product with agents inside it, not a free-form autonomous investigator. Third, the team needs to decide how much near-term effort goes into internal operator tooling versus government-ready packaging. Finally, the team should confirm that Hermes stays in the experimentation lane unless and until its public runtime model matures enough for stronger production guarantees.

## Bottom Line

The plan of action is now clear. CalDS should move forward with a workflow-first architecture anchored on durable execution, bounded agent coordination, deterministic evidence handling, and explicit human review. That path is the best fit for a product that wants to be fast, credible, and eventually sellable into serious oversight environments.

The goal is not to build the most autonomous agent system. The goal is to build the most defensible one.
