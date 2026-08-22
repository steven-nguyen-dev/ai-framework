# Bimodal Author-Side Review Contract

We adopt a bimodal review model for AI-generated code inside team codebases. The human engineer focuses cognitive review on upstream intent and test contract design, plus targeted downstream audit of high-risk surfaces (security, data mutations, state transitions), while delegating mechanical correctness and line-by-line linting/formatting to deterministic checks and adversarial sub-agent review. This balances developer throughput against the verification tax and prevents unreviewed failure modes from reaching team pull requests.
