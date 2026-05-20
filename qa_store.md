# Saved Q&A Answers

<!-- Claude Code will check this file before generating any new answer to a job application question. -->
<!-- To save an answer: tell Claude "save this answer to '[question]'" and it will append below. -->
<!-- Format: ## Q: [question] followed by **A:** [your answer] -->

## Q: Have you ever used or created a system to manage data locks in a database to avoid concurrency issues?
**A:** At Red Cliff Asset Management, we handled concurrency in the market data system through architectural separation at the service layer. We ran a single dedicated backend instance responsible for all writes to the database — ingesting and updating market data feeds — while multiple separate backend instances served read traffic from the trader-facing market watch application and other services.

Because only one backend instance could ever write to the database at a time, write-write conflicts were eliminated by design — no two processes were ever racing to update the same record. The read instances scaled independently to handle concurrent queries from multiple traders without contending with each other or with the writer.

The main consistency concern was ensuring the read instances weren't serving stale data immediately after a write, which we managed through careful service coordination.

