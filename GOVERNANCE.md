# LLMSlim Governance

LLMSlim is an open-source project maintained with a focus on reliability, transparency, security, and long-term sustainability.

The project is currently **maintainer-led**. As the contributor community grows, governance may evolve toward a broader maintainer or technical steering model.

---

## 1. Project Leadership

LLMSlim is currently led and maintained by:

**Yashvardhan Thanvi**
GitHub: [@Thanatos9404](https://github.com/Thanatos9404)

The primary maintainer is responsible for:

* overall project direction and roadmap;
* architecture and technical design decisions;
* reviewing and merging pull requests;
* release management and versioning;
* security policy and vulnerability response;
* repository administration;
* CI/CD and package publishing;
* issue triage and contributor coordination;
* resolving technical or governance disputes.

---

## 2. Decision-Making

LLMSlim aims to make technical decisions openly and based on engineering merit.

For routine changes, decisions are made through normal GitHub issues and pull requests.

Significant changes should ideally be discussed before implementation. This includes:

* public API changes;
* breaking changes;
* major architectural changes;
* security-sensitive behavior;
* new trust or provenance assumptions;
* changes to compression guarantees;
* package or dependency changes that affect the security surface;
* changes to release or publishing infrastructure.

When evaluating proposals, the project considers:

1. correctness;
2. security;
3. backward compatibility;
4. maintainability;
5. performance;
6. testability;
7. impact on users;
8. complexity introduced into the codebase.

The primary maintainer currently has final decision-making authority where consensus cannot be reached.

As the project gains additional maintainers, important decisions should increasingly be made through documented maintainer consensus.

---

## 3. Pull Requests and Merge Authority

All contributors are welcome to open pull requests.

Pull requests should follow the standards described in `CONTRIBUTING.md`, including relevant testing, formatting, typing, documentation, and benchmark requirements.

At present, only the primary maintainer has authority to merge changes into protected project branches.

Security-sensitive changes may require additional review, testing, or discussion before merge.

No contributor should merge their own security-sensitive change without review once the project has more than one maintainer with appropriate review permissions.

---

## 4. Release Authority

Official releases of LLMSlim are currently created by the primary maintainer.

A release should only be published after:

* required CI checks pass;
* tests and coverage requirements are satisfied;
* package artifacts are validated;
* release version information is consistent;
* relevant changelog or release documentation is updated;
* known security regressions have been addressed or explicitly documented.

Package publication should use the project’s approved release workflow and trusted publishing mechanisms wherever possible.

Release credentials, repository secrets, and publishing permissions should be restricted to the minimum number of trusted maintainers necessary.

---

## 5. Security Governance

Security decisions are treated separately from ordinary feature development when necessary.

The primary maintainer currently serves as the project's **security lead** and is responsible for:

* vulnerability triage;
* coordinated disclosure;
* security advisories;
* release decisions for security fixes;
* maintaining `SECURITY.md`;
* reviewing changes that affect trust boundaries;
* evaluating supply-chain risks;
* handling security-sensitive repository permissions.

Potential vulnerabilities should be reported privately through the channels documented in `SECURITY.md`.

Security reports should not be disclosed publicly until a fix, mitigation, or disclosure plan has been prepared unless immediate public disclosure is necessary to protect users.

---

## 6. Security Exceptions

LLMSlim prefers secure-by-default behavior.

Any exception that weakens an established security control should be:

* narrowly scoped;
* documented;
* justified by a clear technical reason;
* reviewed before release;
* temporary where possible;
* accompanied by appropriate tests or compensating controls.

Examples include temporary dependency overrides, disabled security checks, reduced validation, release-process exceptions, or changes that weaken provenance or trust-boundary guarantees.

Security exceptions should never be introduced solely to make CI pass or accelerate a release.

---

## 7. Maintainer Roles

LLMSlim may introduce additional maintainers as the community grows.

A maintainer may be granted responsibilities in one or more areas:

* core library;
* integrations;
* documentation;
* benchmarking;
* security;
* releases;
* website or developer tooling.

Maintainer privileges may include:

* issue and pull request triage;
* merge permissions;
* release permissions;
* security advisory access;
* repository administration.

Access should follow the principle of least privilege.

---

## 8. Becoming a Maintainer

Contributor access is earned through sustained, trustworthy participation rather than through a single contribution.

Potential maintainers should demonstrate:

* consistent high-quality contributions;
* understanding of LLMSlim’s architecture and design goals;
* familiarity with testing and release requirements;
* responsible handling of security-sensitive issues;
* constructive communication with contributors;
* respect for the Code of Conduct;
* willingness to review and maintain code written by others;
* long-term interest in the health of the project.

Maintainer status is granted by the existing project leadership.

Where multiple maintainers exist, new maintainer appointments should be discussed among current maintainers.

---

## 9. Maintainer Inactivity and Removal

Maintainer access may be reduced or removed if a maintainer:

* becomes inactive for an extended period;
* requests removal;
* repeatedly violates project policies;
* misuses repository or release permissions;
* handles security-sensitive information irresponsibly;
* creates a significant risk to users or project integrity.

Whenever practical, these decisions should be discussed privately with the maintainer involved before access is changed.

Security incidents may require immediate access restriction.

---

## 10. Conflicts and Disagreements

Technical disagreement is normal and should be resolved through respectful discussion.

Contributors should focus on:

* evidence;
* reproducible tests;
* user impact;
* security implications;
* compatibility;
* maintainability.

If consensus cannot be reached, the primary maintainer currently makes the final decision.

The rationale for significant decisions should be documented in the relevant issue, pull request, release note, or architecture documentation when useful to future contributors.

Personal conflicts and conduct issues are handled according to the project’s Code of Conduct.

---

## 11. Contributor Expectations

All contributors are expected to:

* follow the Code of Conduct;
* respect project security policies;
* disclose conflicts of interest when relevant;
* avoid knowingly introducing malicious or deceptive code;
* avoid exposing secrets or private vulnerability information;
* provide accurate information in issues and pull requests;
* cooperate with maintainers during reviews and security investigations.

Contributions generated or assisted by automated tools or AI remain the responsibility of the person submitting them.

---

## 12. Governance Changes

This governance document may evolve as LLMSlim grows.

Major governance changes should be proposed publicly where practical and documented through normal repository history.

Future changes may include:

* multiple core maintainers;
* dedicated security maintainers;
* domain-specific maintainers;
* formal voting procedures;
* a technical steering group;
* documented release quorum requirements.

Until such changes are adopted, LLMSlim remains a maintainer-led project.

---

## 13. Governance Principles

LLMSlim governance is guided by the following principles:

* **Security before convenience**
* **Open discussion where possible**
* **Least privilege for sensitive access**
* **Technical merit over hierarchy**
* **Reproducibility over assumptions**
* **Backward compatibility where practical**
* **Clear ownership of security and releases**
* **Transparent evolution of the project**

---

## Contact

For general project discussions, use GitHub Issues or Pull Requests.

For security-related matters, follow the private reporting process described in [`SECURITY.md`](SECURITY.md).

Project repository:
https://github.com/Thanatos9404/llmslim
