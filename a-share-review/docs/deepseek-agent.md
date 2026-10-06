# DeepSeek Agent

The API key is never stored in this repository.

PowerShell:

    $env:DEEPSEEK_API_KEY="<set locally>"
    python run_deepseek_ab.py --date 2026-09-30 --model deepseek-flash

For the higher-quality comparison:

    python run_deepseek_ab.py --date 2026-09-30 --model deepseek-v4-pro

The adapter consumes only frozen Evidence Store data, Skill and Schema.
Its output must still pass Schema, Contract, Evidence Integrity and Independent
Eval. A successful HTTP response is not a successful review.

Security:
- do not put the key in opencode.json, source files, test fixtures or Git
- parent environment is allowlisted before launching the adapter
- unrelated secrets are not inherited
- no automatic retry is performed
