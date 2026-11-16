# ASVS 5.0.0 Level 2 coverage

**Historical baseline:** [STAGING_FINAL.md](STAGING_FINAL.md) contains the current evidence delta, including native MFA/revocation passes and password/transport failures. The counts below have not been inflated into complete compliance; unexecuted requirements remain NOT TESTED.

Baseline: OWASP ASVS stable v5.0.0, including all L1 and L2 requirements (253 rows). This is a conservative evidence register, **not an ASVS Level 2 certification or a claim of completed verification**. PASS applies to the stated local/source evidence; production assurance is separately blocked. NOT TESTED includes partial coverage that does not establish the whole requirement.

Source: https://github.com/OWASP/ASVS/tree/v5.0.0 ; the original CSV is preserved under its CC BY-SA 4.0 license (https://creativecommons.org/licenses/by-sa/4.0/).

Counts: {"PASS": 9, "FAIL": 2, "NOT TESTED": 236, "NOT APPLICABLE": 6}

| Requirement | Level | Section | Result | Evidence / limitation |
|---|---|---|---|---|
| V1.1.1 | 2 | Encoding and Sanitization Architecture | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V1.1.2 | 2 | Encoding and Sanitization Architecture | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V1.2.1 | 1 | Injection Prevention | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V1.2.2 | 1 | Injection Prevention | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V1.2.3 | 1 | Injection Prevention | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V1.2.4 | 1 | Injection Prevention | PASS | ORM/bound raw SQL review; real PostgreSQL SQL-injection negative test; scoped queries. |
| V1.2.5 | 1 | Injection Prevention | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V1.2.6 | 2 | Injection Prevention | NOT APPLICABLE | No LDAP integration. |
| V1.2.7 | 2 | Injection Prevention | NOT APPLICABLE | No XPath processor. |
| V1.2.8 | 2 | Injection Prevention | NOT APPLICABLE | No LaTeX processor. |
| V1.2.9 | 2 | Injection Prevention | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V1.3.1 | 1 | Sanitization | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V1.3.2 | 1 | Sanitization | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V1.3.3 | 2 | Sanitization | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V1.3.4 | 2 | Sanitization | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V1.3.5 | 2 | Sanitization | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V1.3.6 | 2 | Sanitization | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V1.3.7 | 2 | Sanitization | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V1.3.8 | 2 | Sanitization | NOT APPLICABLE | No Java/JNDI runtime. |
| V1.3.9 | 2 | Sanitization | NOT APPLICABLE | No memcache integration. |
| V1.3.10 | 2 | Sanitization | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V1.3.11 | 2 | Sanitization | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V1.4.1 | 2 | Memory, String, and Unmanaged Code | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V1.4.2 | 2 | Memory, String, and Unmanaged Code | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V1.4.3 | 2 | Memory, String, and Unmanaged Code | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V1.5.1 | 1 | Safe Deserialization | NOT APPLICABLE | No application XML parsing of untrusted input. |
| V1.5.2 | 2 | Safe Deserialization | PASS | Strict request schemas; no unsafe pickle/eval/XML deserialization in application scan. |
| V2.1.1 | 1 | Validation and Business Logic Documentation | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V2.1.2 | 2 | Validation and Business Logic Documentation | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V2.1.3 | 2 | Validation and Business Logic Documentation | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V2.2.1 | 1 | Input Validation | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V2.2.2 | 1 | Input Validation | PASS | Real API mass-assignment/price negative tests; server service validation. |
| V2.2.3 | 2 | Input Validation | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V2.3.1 | 1 | Business Logic Security | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V2.3.2 | 2 | Business Logic Security | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V2.3.3 | 2 | Business Logic Security | PASS | Transactional workflow/concurrency and migration round-trip regressions. |
| V2.3.4 | 2 | Business Logic Security | PASS | Concurrent slot winner tests plus intentional, scoped employee overlap tests. |
| V2.4.1 | 2 | Anti-automation | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V3.2.1 | 1 | Unintended Content Interpretation | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V3.2.2 | 1 | Unintended Content Interpretation | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V3.3.1 | 1 | Cookie Setup | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V3.3.2 | 2 | Cookie Setup | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V3.3.3 | 2 | Cookie Setup | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V3.3.4 | 2 | Cookie Setup | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V3.4.1 | 1 | Browser Security Mechanism Headers | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V3.4.2 | 1 | Browser Security Mechanism Headers | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V3.4.3 | 2 | Browser Security Mechanism Headers | FAIL | CSP added, but unsafe-inline remains for Next/Expo compatibility; nonce/hash migration still required for strong CSP. |
| V3.4.4 | 2 | Browser Security Mechanism Headers | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V3.4.5 | 2 | Browser Security Mechanism Headers | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V3.4.6 | 2 | Browser Security Mechanism Headers | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V3.5.1 | 1 | Browser Origin Separation | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V3.5.2 | 1 | Browser Origin Separation | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V3.5.3 | 1 | Browser Origin Separation | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V3.5.4 | 2 | Browser Origin Separation | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V3.5.5 | 2 | Browser Origin Separation | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V3.7.1 | 2 | Other Browser Security Considerations | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V3.7.2 | 2 | Other Browser Security Considerations | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V4.1.1 | 1 | Generic Web Service Security | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V4.1.2 | 2 | Generic Web Service Security | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V4.1.3 | 2 | Generic Web Service Security | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V4.2.1 | 2 | HTTP Message Structure Validation | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V4.3.1 | 2 | GraphQL | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V4.3.2 | 2 | GraphQL | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V4.4.1 | 1 | WebSocket | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V4.4.2 | 2 | WebSocket | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V4.4.3 | 2 | WebSocket | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V4.4.4 | 2 | WebSocket | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V5.1.1 | 2 | File Handling Documentation | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V5.2.1 | 1 | File Upload and Content | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V5.2.2 | 1 | File Upload and Content | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V5.2.3 | 2 | File Upload and Content | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V5.3.1 | 1 | File Storage | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V5.3.2 | 1 | File Storage | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V5.4.1 | 2 | File Download | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V5.4.2 | 2 | File Download | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V5.4.3 | 2 | File Download | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V6.1.1 | 1 | Authentication Documentation | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V6.1.2 | 2 | Authentication Documentation | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V6.1.3 | 2 | Authentication Documentation | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V6.2.1 | 1 | Password Security | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V6.2.2 | 1 | Password Security | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V6.2.3 | 1 | Password Security | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V6.2.4 | 1 | Password Security | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V6.2.5 | 1 | Password Security | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V6.2.6 | 1 | Password Security | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V6.2.7 | 1 | Password Security | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V6.2.8 | 1 | Password Security | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V6.2.9 | 2 | Password Security | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V6.2.10 | 2 | Password Security | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V6.2.11 | 2 | Password Security | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V6.2.12 | 2 | Password Security | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V6.3.1 | 1 | General Authentication Security | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V6.3.2 | 1 | General Authentication Security | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V6.3.3 | 2 | General Authentication Security | FAIL | Privileged MFA enforcement/enrollment is absent; see F17. |
| V6.3.4 | 2 | General Authentication Security | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V6.4.1 | 1 | Authentication Factor Lifecycle and Recovery | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V6.4.2 | 1 | Authentication Factor Lifecycle and Recovery | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V6.4.3 | 2 | Authentication Factor Lifecycle and Recovery | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V6.4.4 | 2 | Authentication Factor Lifecycle and Recovery | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V6.5.1 | 2 | General Multi-factor authentication requirements | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V6.5.2 | 2 | General Multi-factor authentication requirements | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V6.5.3 | 2 | General Multi-factor authentication requirements | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V6.5.4 | 2 | General Multi-factor authentication requirements | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V6.5.5 | 2 | General Multi-factor authentication requirements | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V6.6.1 | 2 | Out-of-Band authentication mechanisms | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V6.6.2 | 2 | Out-of-Band authentication mechanisms | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V6.6.3 | 2 | Out-of-Band authentication mechanisms | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V6.8.1 | 2 | Authentication with an Identity Provider | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V6.8.2 | 2 | Authentication with an Identity Provider | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V6.8.3 | 2 | Authentication with an Identity Provider | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V6.8.4 | 2 | Authentication with an Identity Provider | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V7.1.1 | 2 | Session Management Documentation | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V7.1.2 | 2 | Session Management Documentation | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V7.1.3 | 2 | Session Management Documentation | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V7.2.1 | 1 | Fundamental Session Management Security | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V7.2.2 | 1 | Fundamental Session Management Security | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V7.2.3 | 1 | Fundamental Session Management Security | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V7.2.4 | 1 | Fundamental Session Management Security | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V7.3.1 | 2 | Session Timeout | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V7.3.2 | 2 | Session Timeout | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V7.4.1 | 1 | Session Termination | PASS | Authoritative session row revocation/bans and actual API replay-denial test locally. |
| V7.4.2 | 1 | Session Termination | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V7.4.3 | 2 | Session Termination | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V7.4.4 | 2 | Session Termination | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V7.4.5 | 2 | Session Termination | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V7.5.1 | 2 | Defenses Against Session Abuse | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V7.5.2 | 2 | Defenses Against Session Abuse | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V7.6.1 | 2 | Federated Re-authentication | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V7.6.2 | 2 | Federated Re-authentication | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V8.1.1 | 1 | Authorization Documentation | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V8.1.2 | 2 | Authorization Documentation | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V8.2.1 | 1 | General Authorization Design | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V8.2.2 | 1 | General Authorization Design | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V8.2.3 | 2 | General Authorization Design | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V8.3.1 | 1 | Operation Level Authorization | PASS | Authoritative SQL staff role, real customer/team/tenant negative tests; 144 anonymous denials. |
| V8.4.1 | 2 | Other Authorization Considerations | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V9.1.1 | 1 | Token source and integrity | PASS | Actual signed JWT and management/review capability signature tests. |
| V9.1.2 | 1 | Token source and integrity | PASS | Fixed algorithm allowlists and invalid-signature tests. |
| V9.1.3 | 1 | Token source and integrity | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V9.2.1 | 1 | Token content | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V9.2.2 | 2 | Token content | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V9.2.3 | 2 | Token content | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V9.2.4 | 2 | Token content | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V10.1.1 | 2 | Generic OAuth and OIDC Security | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V10.1.2 | 2 | Generic OAuth and OIDC Security | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V10.2.1 | 2 | OAuth Client | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V10.2.2 | 2 | OAuth Client | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V10.3.1 | 2 | OAuth Resource Server | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V10.3.2 | 2 | OAuth Resource Server | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V10.3.3 | 2 | OAuth Resource Server | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V10.3.4 | 2 | OAuth Resource Server | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V10.4.1 | 1 | OAuth Authorization Server | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V10.4.2 | 1 | OAuth Authorization Server | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V10.4.3 | 1 | OAuth Authorization Server | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V10.4.4 | 1 | OAuth Authorization Server | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V10.4.5 | 1 | OAuth Authorization Server | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V10.4.6 | 2 | OAuth Authorization Server | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V10.4.7 | 2 | OAuth Authorization Server | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V10.4.8 | 2 | OAuth Authorization Server | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V10.4.9 | 2 | OAuth Authorization Server | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V10.4.10 | 2 | OAuth Authorization Server | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V10.4.11 | 2 | OAuth Authorization Server | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V10.5.1 | 2 | OIDC Client | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V10.5.2 | 2 | OIDC Client | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V10.5.3 | 2 | OIDC Client | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V10.5.4 | 2 | OIDC Client | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V10.5.5 | 2 | OIDC Client | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V10.6.1 | 2 | OpenID Provider | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V10.6.2 | 2 | OpenID Provider | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V10.7.1 | 2 | Consent Management | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V10.7.2 | 2 | Consent Management | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V10.7.3 | 2 | Consent Management | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V11.1.1 | 2 | Cryptographic Inventory and Documentation | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V11.1.2 | 2 | Cryptographic Inventory and Documentation | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V11.2.1 | 2 | Secure Cryptography Implementation | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V11.2.2 | 2 | Secure Cryptography Implementation | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V11.2.3 | 2 | Secure Cryptography Implementation | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V11.3.1 | 1 | Encryption Algorithms | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V11.3.2 | 1 | Encryption Algorithms | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V11.3.3 | 2 | Encryption Algorithms | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V11.4.1 | 1 | Hashing and Hash-based Functions | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V11.4.2 | 2 | Hashing and Hash-based Functions | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V11.4.3 | 2 | Hashing and Hash-based Functions | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V11.4.4 | 2 | Hashing and Hash-based Functions | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V11.5.1 | 2 | Random Values | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V11.6.1 | 2 | Public Key Cryptography | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V12.1.1 | 1 | General TLS Security Guidance | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V12.1.2 | 2 | General TLS Security Guidance | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V12.1.3 | 2 | General TLS Security Guidance | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V12.2.1 | 1 | HTTPS Communication with External Facing Services | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V12.2.2 | 1 | HTTPS Communication with External Facing Services | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V12.3.1 | 2 | General Service to Service Communication Security | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V12.3.2 | 2 | General Service to Service Communication Security | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V12.3.3 | 2 | General Service to Service Communication Security | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V12.3.4 | 2 | General Service to Service Communication Security | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V13.1.1 | 2 | Configuration Documentation | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V13.2.1 | 2 | Backend Communication Configuration | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V13.2.2 | 2 | Backend Communication Configuration | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V13.2.3 | 2 | Backend Communication Configuration | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V13.2.4 | 2 | Backend Communication Configuration | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V13.2.5 | 2 | Backend Communication Configuration | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V13.3.1 | 2 | Secret Management | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V13.3.2 | 2 | Secret Management | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V13.4.1 | 1 | Unintended Information Leakage | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V13.4.2 | 2 | Unintended Information Leakage | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V13.4.3 | 2 | Unintended Information Leakage | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V13.4.4 | 2 | Unintended Information Leakage | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V13.4.5 | 2 | Unintended Information Leakage | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V14.1.1 | 2 | Data Protection Documentation | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V14.1.2 | 2 | Data Protection Documentation | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V14.2.1 | 1 | General Data Protection | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V14.2.2 | 2 | General Data Protection | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V14.2.3 | 2 | General Data Protection | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V14.2.4 | 2 | General Data Protection | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V14.3.1 | 1 | Client-side Data Protection | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V14.3.2 | 2 | Client-side Data Protection | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V14.3.3 | 2 | Client-side Data Protection | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V15.1.1 | 1 | Secure Coding and Architecture Documentation | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V15.1.2 | 2 | Secure Coding and Architecture Documentation | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V15.1.3 | 2 | Secure Coding and Architecture Documentation | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V15.2.1 | 1 | Security Architecture and Dependencies | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V15.2.2 | 2 | Security Architecture and Dependencies | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V15.2.3 | 2 | Security Architecture and Dependencies | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V15.3.1 | 1 | Defensive Coding | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V15.3.2 | 2 | Defensive Coding | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V15.3.3 | 2 | Defensive Coding | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V15.3.4 | 2 | Defensive Coding | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V15.3.5 | 2 | Defensive Coding | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V15.3.6 | 2 | Defensive Coding | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V15.3.7 | 2 | Defensive Coding | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V16.1.1 | 2 | Security Logging Documentation | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V16.2.1 | 2 | General Logging | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V16.2.2 | 2 | General Logging | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V16.2.3 | 2 | General Logging | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V16.2.4 | 2 | General Logging | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V16.2.5 | 2 | General Logging | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V16.3.1 | 2 | Security Events | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V16.3.2 | 2 | Security Events | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V16.3.3 | 2 | Security Events | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V16.3.4 | 2 | Security Events | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V16.4.1 | 2 | Log Protection | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V16.4.2 | 2 | Log Protection | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V16.4.3 | 2 | Log Protection | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V16.5.1 | 2 | Error Handling | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V16.5.2 | 2 | Error Handling | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V16.5.3 | 2 | Error Handling | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V17.1.1 | 2 | TURN Server | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V17.2.1 | 2 | Media | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V17.2.2 | 2 | Media | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V17.2.3 | 2 | Media | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V17.2.4 | 2 | Media | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V17.3.1 | 2 | Signaling | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
| V17.3.2 | 2 | Signaling | NOT TESTED | Requirement not fully verified; code review and selected tests do not establish this entire control. See report limitations/manual release gate. |
