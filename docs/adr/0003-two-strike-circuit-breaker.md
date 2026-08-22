# Two-Strike Circuit Breaker and Clean Rollback

We enforce an automated circuit breaker that halts agent execution and reverts uncommitted changes to baseline after two consecutive verification failures. Rather than allowing agents to enter unconstrained self-correction loops that pollute context and snowball into sprawling refactors, early rollback forces clean state resets and prompts the human orchestrator for structural steering.
