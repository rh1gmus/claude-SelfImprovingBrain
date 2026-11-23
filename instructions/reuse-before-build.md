# Reuse before build (INSTRUCTION SET: tunable) 
Before scaffolding a new project, Dockerfile, compose stack, or script >~30 lines,
check for prior art first: [I-065]
1. My own existing repos/projects
2. Official/vendor images, compose files, Helm charts; linuxserver.io
3. GitHub, awesome-selfhosted, PowerShell Gallery

Show 2–4 options (adopt / wrap-or-fork / build) with fit, maintenance (last ~12 mo),
license, and trust. [I-066]
Prefer adopt → wrap → fork → build. [I-067]
Recommend building only if existing options are unmaintained, badly licensed, untrusted, or cover under ~half the need. [I-068]
Note what was considered in the README. [I-069]

Skip when I say "from scratch," "greenfield," or "learning build," for trivial or
one-off tasks, or if already checked this session. [I-070]
Keep it to a few searches. [I-071]
If I'm not around, take the recommended option and say so. [I-072]
