# CalDS Eval Harness and Operator Guide

## Why This Pack Exists

The evaluation pack is not there to make the prompt system look tidy. It exists to answer a harder operational question: if CalDS is going to route politically sensitive, evidence-bound work through specialist agents, how will the team know when the system has drifted, when a prompt change made the system sloppier, or when a supposedly helpful improvement actually weakened the review boundary?

That is why the harness matters. It creates a repeatable check between prompt revisions, agent-role boundaries, and expected safety behavior. In other words, it turns prompt editing from a vibes exercise into a regression discipline.

## What This Harness Actually Tests

At a practical level, the harness checks whether the stack still produces the right structure, preserves the evidence boundary, avoids accusation drift, and keeps sentinel-style gating intact. The included run directory is useful because it shows not only what the system was asked to do, but also how cleanly each agent stayed inside its lane.

The important thing to remember is that these cases are not meant to prove truth in the outside world. They are meant to prove runtime discipline inside the system. A passing case tells you that the agent behaved correctly given the constraints. A failing case tells you exactly where the stack became unsafe, underspecified, or too eager.

## How To Read The Pack

Start with the two README files. They explain the contract of the harness, what a run directory should contain, and what minimum metadata belongs with a serious evaluation pass. After that, review the baseline case outputs in role order rather than file-name order. Read the case-director outputs first, then retrieval design, then network and evidence handling, then lead scoring, then sentinel decisions, and finally the review packet.

That sequence matters because it mirrors how the full system is supposed to behave in production. The safest way to evaluate a multi-agent stack is to judge each boundary in the order decisions are made.

## What A Good Run Looks Like

A good run should feel narrow, skeptical, and boring in the best sense. The coordinator should shrink vague or accusatory requests into bounded case scopes. Retrieval should stay inside allowed sources. Network analysis should separate hard links from soft links. Evidence analysis should clearly distinguish contradiction, ambiguity, and missing data. Lead scoring should penalize weak linkage instead of rewarding excitement. Sentinel should block or downgrade anything that reads stronger than the evidence supports. The review packet should read like material prepared for internal review, not publication copy.

If any one of those steps becomes too loose, the entire system becomes harder to defend. That is why this pack should be read as a chain, not as isolated agent outputs.

## How To Use It During Prompt Changes

Whenever the team changes a prompt, routing rule, scoring rule, or evidence policy, the harness should be rerun against a stable case set before the change is accepted. The objective is not only to see whether output quality improved. The objective is to see whether the stack preserved the same structural guarantees.

A simple rule works well here: do not ship a prompt change just because one answer feels better. Ship it only if the regression pack still shows the same lane discipline, the same review safety, and the same ability to admit uncertainty when evidence is weak.

## What To Improve Next

The current pack is a solid baseline, but it should grow in three directions. First, it should add more difficult retrieval and contradiction cases, especially ones that test stale evidence, partial entity overlap, and politically charged requests. Second, it should add evaluation metadata that ties each run to a prompt version, model version, and operator notes more rigorously. Third, it should eventually connect to the future runtime architecture so that trace data, reviewer decisions, and harness results can be compared in one place.

That next step will matter once CalDS moves from prompt design into runtime implementation, because the same evaluation habit should continue when the system becomes a real workflow product.

## Why This Matters

The harness is the operational conscience of the system. It is the thing that makes it possible to improve the agents without forgetting why the agents were constrained in the first place. The more serious the product becomes, the more this pack should be treated as a release gate rather than optional documentation.
