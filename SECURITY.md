# MoOS security and official releases

بلّغ عن الثغرات بشكل خاص عبر [التبليغ الأمني على GitHub](https://github.com/moalfarras-sys/moos-image/security/advisories/new).
اكتب الإصدار وخطوات إعادة المشكلة وأرفق سجلًا منقّحًا. لا ترسل كلمات المرور أو
مفاتيح API أو المفاتيح الخاصة، ولا تنشر تفاصيل استغلال نشط في issue عامة.

Use [private vulnerability reporting](https://github.com/moalfarras-sys/moos-image/security/advisories/new)
for reproducible security defects. Include the installed version, reproduction
steps and redacted logs. Account credentials and signing private keys are never
needed in a report. Ordinary bugs belong in the issue tracker.

Official images enforce the public key represented by `cosign.pub`. Verify the
exact image digest and its signature using the official release instructions in
[RELEASE.md](RELEASE.md). A copied logo, passing CI or a fork's own signature does
not identify an official MoOS release. Keep the signed rollback deployment.

Repository write access is limited to the maintainer. Main requires the repository
gate, including for administrators; force pushes and branch deletion are blocked.
Secret scanning and push protection are enabled. Dependency vulnerability alerts,
proposed security fixes and private reporting were enabled and read back on
2026-10-16. Proposed fixes still need review and the normal signed release proofs.

Top-level workflow actions are fixed to the upstream commits recorded in
`.github/action-pins.json`. Checkout does not retain credentials in the worktree.
Secret-bearing AI jobs require the repository owner; fork PRs cannot enter the
advisory credential job. `tests/test_workflow_security.py` checks the maintained
workflows and rejects isolated moving-tag, unreviewed-pin, credential-persistence
and authorization-bypass controls. This does not audit every dependency or download
inside a third-party action. Upstream changes still require review.

Software and artwork rights remain as described in [OWNERSHIP.md](OWNERSHIP.md)
and each component's existing licence. Public source can be viewed and forked;
these controls protect access, credentials and official delivery. They do not
prevent copying published source or change upstream licence rights.

Primary references:
[GitHub workflow security](https://docs.github.com/en/actions/reference/security/secure-use),
[secret scanning](https://docs.github.com/en/code-security/concepts/secret-security/secret-scanning),
[licensing a public repository](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository).
