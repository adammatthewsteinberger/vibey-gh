# Claude guidance

Follow `AGENTS.md` as the canonical policy. Use the configured `vibey-skills` marketplace
for architecture, security, engineering-process, and quality-engineering work. Claude
jobs with write credentials may edit only the scope named by their workflow prompt; a
separate guarded step performs commits and pushes. Never execute contributor-controlled
code in a privileged job.
