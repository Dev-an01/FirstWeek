# Information Security Policy

**Document ID**: POLICY-IT-001  
**Version**: 3.0  
**Effective Date**: October 1, 2024  
**Owner**: CTO Office (Yuki Nakamura)  
**Last Updated**: October 1, 2024 (Post-Security Incident)  
**Review Frequency**: Quarterly  
**Confidentiality**: Internal

---

## 1. Purpose

This policy establishes information security standards to protect:
- Customer data and privacy
- Company intellectual property
- Employee personal information
- Business operations and systems

**Zero tolerance**: Security violations are taken extremely seriously and may result in immediate termination.

---

## 2. Scope

Applies to:
- All NexaTech employees, contractors, and vendors
- All company devices and systems
- All data (customer, company, employee)
- All locations (office, home, public)

---

## 3. Data Classification

### 3.1 Classification Levels

| Level | Definition | Examples | Handling |
|-------|------------|----------|----------|
| **Public** | Information freely shareable | Marketing materials, public blog posts, press releases | No restrictions |
| **Internal** | Information for employees only | Company org chart, internal docs, policies | Employee access only, no external sharing |
| **Confidential** | Sensitive business information | Financial data, strategy docs, customer lists | Need-to-know basis, encrypted storage |
| **Restricted** | Highly sensitive data | Customer PII, payment info, source code, security credentials | Strict access controls, encrypted at rest & transit, audit logging |

### 3.2 Customer Data (Always Restricted)

Customer data includes:
- Personal information (names, emails, phone numbers)
- Usage data and analytics
- Customer content and files
- Billing and payment information
- Any data submitted by customers to our products

**Handling requirements**:
- ✓ Access only when required for job function
- ✓ Never download to personal devices
- ✓ Never share via unencrypted channels
- ✓ Never discuss in public places
- ✓ Delete when no longer needed
- ✓ Report breaches immediately

---

## 4. Access Control

### 4.1 Account Management

**User Accounts**:
- Unique account per employee (no shared accounts)
- Strong passwords required (min 14 characters, complexity requirements)
- Password managers mandatory (1Password provided)
- Multi-factor authentication (2FA/MFA) required for:
  - Email accounts
  - VPN access
  - Production systems
  - Cloud services (AWS, GCP)
  - Code repositories
  - Admin consoles

**Password Standards**:
- Minimum 14 characters
- Mix of uppercase, lowercase, numbers, symbols
- No dictionary words
- No reuse across systems
- Change every 90 days for admin accounts
- Never share passwords (even with IT)

### 4.2 Principle of Least Privilege

Access granted based on:
- Job role requirements
- Need-to-know basis
- Time-limited (revoked when no longer needed)

**Production access**:
- Engineers: Read-only by default
- Write access: Requires manager approval + security training
- Database access: Audit logged, reviewed quarterly

### 4.3 Access Reviews

**Quarterly reviews**:
- Managers review team access permissions
- Revoke unnecessary access
- Document business justification for elevated access

**Immediate revocation**:
- Termination: Within 1 hour
- Role change: Within 24 hours
- Leave of absence: Temporary suspension

---

## 5. Device Security

### 5.1 Company Devices

**Required security measures**:
- ☐ Full disk encryption (FileVault/BitLocker)
- ☐ Auto-lock after 5 minutes
- ☐ Biometric or strong password login
- ☐ Antivirus/EDR software (company-provided)
- ☐ Automatic security updates enabled
- ☐ Firewall enabled
- ☐ Screen privacy filter (for public work)

**Prohibited on company devices**:
- ❌ Unauthorized software installation
- ❌ Jailbreaking/rooting
- ❌ Disabling security features
- ❌ Personal use for sensitive activities
- ❌ Storing personal sensitive data

### 5.2 Mobile Devices (BYOD)

**If accessing company email on personal device**:
- Must use mobile device management (MDM)
- Must enable device encryption
- Must use strong password/biometric
- Company can remotely wipe corporate data (only)

**Prohibited**:
- Accessing customer data on personal devices
- Downloading customer files to personal devices
- Using personal devices for production access

### 5.3 Lost or Stolen Devices

**Immediate action required**:
1. Report to IT within 1 hour: it-security@nexatech.jp
2. IT will remotely wipe device
3. Change all passwords immediately
4. File police report (if stolen)

**No penalty** for reporting lost/stolen device promptly.

---

## 6. Network Security

### 6.1 VPN Usage

**VPN required when**:
- Working from home
- Accessing internal systems remotely
- Using public WiFi
- Accessing production environments

**VPN not required**:
- Office network (already secured)
- Public websites/SaaS tools (non-company data)

### 6.2 WiFi Security

**Company office WiFi**:
- WPA3 encryption
- Unique credentials per employee
- Guest network separate (no internal access)

**Home WiFi recommendations**:
- WPA2/WPA3 encryption minimum
- Change default router password
- Disable WPS
- Guest network for visitors

**Public WiFi**:
- ⚠️ Never use without VPN for company work
- ⚠️ Never access sensitive data
- ⚠️ Assume it's monitored/compromised

### 6.3 Network Monitoring

Company monitors:
- Firewall logs (anomaly detection)
- VPN connections (unusual patterns)
- Internal network traffic (threats)
- Failed login attempts (brute force attempts)

**Privacy commitment**: We don't monitor:
- Personal browsing (on personal time/devices)
- Private messages/emails
- Individual productivity tracking

---

## 7. Application Security

### 7.1 Secure Development

**Engineering requirements**:
- Code review required (100% of PRs)
- Automated security scanning (SAST/DAST)
- Dependency vulnerability scanning
- No secrets in code (use secrets manager)
- Input validation on all user data
- Output encoding to prevent XSS
- Parameterized queries (prevent SQL injection)
- Principle of least privilege for services

### 7.2 Security Testing

**Required before production**:
- Unit tests including security cases
- Integration tests
- Security-focused QA testing
- Penetration testing (quarterly for public-facing)

**External audits**:
- Annual penetration test by external firm
- Quarterly vulnerability assessments
- Remediation plan for critical/high findings

### 7.3 Vulnerability Management

**Response timelines**:
- **Critical** (CVSS 9-10): Patch within 24 hours
- **High** (CVSS 7-8.9): Patch within 7 days
- **Medium** (CVSS 4-6.9): Patch within 30 days
- **Low** (CVSS 0-3.9): Patch within 90 days

**Zero-day vulnerabilities**:
- Emergency response team activated
- CTO notified immediately
- Patch/mitigation within 4 hours

---

## 8. Incident Response

### 8.1 Security Incident Definition

A security incident includes:
- Unauthorized access to systems/data
- Data breach or exfiltration
- Malware infection
- Phishing attack (successful)
- Lost/stolen device with company data
- Insider threat
- Denial of service attack
- Any suspected security compromise

### 8.2 Incident Reporting

**How to report**:
- **Email**: security-incident@nexatech.jp
- **Slack**: @security-team
- **Phone**: IT emergency line (24/7)

**What to report**:
- What happened (be specific)
- When did it occur
- What systems/data affected
- Any actions taken
- Your contact info

**Timeline**: Report immediately upon discovery (within 1 hour)

**No penalty** for good-faith reporting. Delay in reporting is policy violation.

### 8.3 Incident Response Process

**1. Detection & Reporting** (Hour 0)
- Incident reported to security team
- Security engineer on-call notified
- Initial assessment (severity classification)

**2. Containment** (Hours 0-2)
- Isolate affected systems
- Prevent further damage
- Preserve evidence
- CTO notified if severity high/critical

**3. Investigation** (Hours 2-24)
- Determine scope (what data accessed/exfiltrated)
- Identify attack vector
- Document timeline
- Assess impact

**4. Eradication** (Hours 24-72)
- Remove malware/backdoors
- Patch vulnerabilities
- Reset compromised credentials
- Verify systems clean

**5. Recovery** (Days 2-7)
- Restore systems from clean backups
- Verify functionality
- Monitor for recurrence
- Gradually restore access

**6. Post-Incident** (Week 2)
- Root cause analysis
- Post-mortem documentation
- Remediation plan
- Policy/process updates
- Employee communication/training

### 8.4 Customer Notification

**If customer data affected**:
- Notification within 72 hours (regulatory requirement)
- CTO + CEO decide on notification approach
- Transparent communication (see DC_YUKI_005 precedent)
- Offer identity monitoring if appropriate
- Public disclosure on blog if material

**Notification includes**:
- What happened (facts)
- What data was affected
- When it occurred
- What we're doing about it
- How to protect yourself
- Contact for questions

---

## 9. Data Protection

### 9.1 Data Encryption

**Required encryption**:
- **At rest**: All databases, file storage, backups
- **In transit**: TLS 1.2+ for all data transmission
- **Emails**: Encrypted for confidential/restricted data
- **Backups**: Encrypted with separate key

**Encryption standards**:
- AES-256 for data at rest
- TLS 1.2+ for data in transit
- Keys rotated annually
- Keys stored in secrets manager (not code)

### 9.2 Data Retention

**Customer data**:
- Retained as long as customer is active
- Deleted within 30 days of account cancellation (unless legal hold)
- Backups retained 90 days (then overwritten)

**Employee data**:
- Retained during employment + 7 years (tax/legal requirements)
- Deleted after retention period

**Logs and monitoring**:
- Security logs: 1 year
- Application logs: 90 days
- Audit logs: 7 years

### 9.3 Data Deletion

**Secure deletion**:
- Overwrite data 7 times (DoD 5220.22-M standard)
- Destroy physical media (hard drives shredded)
- Certificate of destruction for hardware
- Verify deletion completed

---

## 10. Third-Party Security

### 10.1 Vendor Risk Assessment

**Before engaging vendor with access to data**:
- ☐ Security questionnaire completed
- ☐ SOC 2 Type II report reviewed (or equivalent)
- ☐ Data processing agreement signed
- ☐ Insurance verification ($1M+ cyber liability)
- ☐ Incident response plan reviewed

**Risk tiers**:
- **High risk** (access to customer data): Full assessment + annual review
- **Medium risk** (internal data only): Questionnaire + bi-annual review
- **Low risk** (no data access): Questionnaire only

### 10.2 Vendor Monitoring

- Annual security reviews for high-risk vendors
- Notification requirement if vendor has breach
- Right to audit in contract
- Termination clause for security failures

---

## 11. Physical Security

### 11.1 Office Access

**Access control**:
- Badge required for entry
- Visitor sign-in and escort required
- No tailgating (report violations)
- Cameras in common areas (not private offices)

**Clean desk policy**:
- Lock screens when leaving desk
- No sensitive documents left out
- Shred confidential papers
- Lock filing cabinets

### 11.2 Visitor Management

**Visitors must**:
- Sign in at reception
- Wear visitor badge
- Be escorted by employee at all times
- No access to sensitive areas (data center, server rooms)

**Customer visits**:
- NDA signed before facility tour
- No photography in work areas without approval

---

## 12. Email and Communication Security

### 12.1 Email Security

**Identifying phishing**:
- ⚠️ Sender address doesn't match (hover to check)
- ⚠️ Urgent requests for credentials/money
- ⚠️ Suspicious attachments or links
- ⚠️ Grammar/spelling errors
- ⚠️ Unusual requests from known contacts

**If suspected phishing**:
1. Don't click links or open attachments
2. Forward to security-phishing@nexatech.jp
3. Delete from inbox
4. Report to IT if you clicked (no penalty!)

**Email classification**:
- Use [CONFIDENTIAL] tag for sensitive emails
- Don't email restricted data (use secure file share)
- BCC when sending to external groups (privacy)

### 12.2 Slack/Chat Security

**Best practices**:
- Don't share passwords/credentials in Slack (even DMs)
- Use private channels for confidential discussions
- External guests: Restricted to specific channels
- No customer data in Slack (links to systems OK)

### 12.3 File Sharing

**Approved methods**:
- Internal: Google Drive (company domain)
- External: Secure file share service (encrypted links)
- Large files: Company file transfer service

**Prohibited**:
- Personal Dropbox/Google Drive
- WeTransfer or similar public services
- USB drives for sensitive data
- Unencrypted email attachments (for restricted data)

---

## 13. Remote Work Security

### 13.1 Home Office Security

**Requirements**:
- Private workspace (not shared)
- Lock computer when away
- Shred confidential documents at home
- No family/friends using company devices
- VPN for all company work

### 13.2 Public Spaces

**Allowed with precautions**:
- Use privacy screen filter
- Use VPN
- Be aware of shoulder surfers
- Use headphones for confidential calls

**Prohibited**:
- Accessing restricted customer data
- Discussing confidential matters on calls
- Leaving devices unattended

---

## 14. Social Engineering

### 14.1 Common Tactics

**Be alert for**:
- Impersonation (fake CEO emails requesting wire transfer)
- Pretexting (fake IT calling for password)
- Baiting (USB drives left in parking lot)
- Quid pro quo (fake "system upgrade" requiring login)
- Tailgating (following employee through secure door)

### 14.2 Verification Procedures

**For unusual requests**:
- Verify through secondary channel (call back on known number)
- Never provide password/credentials (IT never asks)
- Confirm large wire transfers face-to-face or video call
- When in doubt, report to security team

---

## 15. Security Training

### 15.1 Required Training

**All employees**:
- Security awareness training: Within 7 days of hire
- Annual refresher training
- Phishing simulation tests (quarterly)
- Policy acknowledgment (annual)

**Engineering/IT**:
- Secure coding training (annually)
- OWASP Top 10 training
- Security testing techniques
- Incident response procedures

**High-risk roles** (Finance, HR, Executives):
- Advanced social engineering awareness
- Fraud prevention training
- Targeted phishing defense

### 15.2 Training Effectiveness

**Metrics tracked**:
- Training completion rate (target: 100%)
- Phishing simulation click rate (target: <5%)
- Time to report suspected phish (target: <1 hour)
- Security quiz scores (target: 90%+)

---

## 16. Compliance and Auditing

### 16.1 Regulatory Compliance

NexaTech complies with:
- **Japan Privacy Law** (APPI) - Personal data protection
- **GDPR** (EU customers) - Data privacy rights
- **SOC 2 Type II** - Security controls audit
- **ISO 27001** (target 2025) - Information security management

### 16.2 Internal Audits

**Frequency**:
- Access reviews: Quarterly
- Security logs review: Monthly
- Penetration testing: Quarterly
- Policy compliance: Annual

**External audits**:
- SOC 2 audit: Annual
- Penetration test: Annual (by external firm)
- ISO 27001 certification audit: Bi-annual (after certification)

### 16.3 Audit Logging

**Logged activities**:
- Authentication attempts (success/failure)
- Access to customer data (who, what, when)
- Administrative actions
- Configuration changes
- Data exports/downloads

**Log retention**: 1 year (security), 7 years (audit logs)

**Log protection**: Immutable, encrypted, access restricted

---

## 17. Security Incident Post-Mortem (DC_YUKI_005)

### 17.1 September 2024 SQL Injection Breach

**What happened**:
- SQL injection vulnerability in legacy admin panel (6 years old)
- Attacker accessed 15,247 customer records (names, emails, company names)
- No passwords, payment info, or usage data accessed
- Detected within 3 hours, attacker access terminated

**Root causes**:
- Legacy code not included in regular security audits
- No rate limiting on admin panel
- Insufficient access logging
- SQL injection not caught by automated scanners

**Immediate actions taken**:
- Patched vulnerability within 2 hours
- Locked down admin panel
- Rotated all admin credentials
- Full disclosure to affected customers within 24 hours
- Offered 12-month identity monitoring

**Preventive measures implemented**:
- All legacy code audited (found 8 additional vulnerabilities, patched)
- Rate limiting on all APIs and admin panels
- Enhanced access logging and monitoring
- Quarterly penetration testing (was annual)
- Security training for all engineers
- Quarterly security audits (was annual)

**Lessons learned**:
- Legacy code is security risk - must audit regularly
- Detection is critical but prevention is better
- Transparency builds trust - full disclosure was right call
- Radical transparency (CEO value) applied to security incident

**Policy updates from this incident**:
- Quarterly security audits (Section 16.2)
- Mandatory security training (Section 15.1)
- Enhanced vulnerability management (Section 7.3)
- Incident response refined (Section 8.3)

---

## 18. Bring Your Own Device (BYOD)

### 18.1 BYOD Policy

**Allowed for**:
- Email access only
- Calendar and contacts
- Slack (with restrictions)

**Prohibited for**:
- Customer data access
- Production system access
- Code repositories
- Internal file shares with restricted data

### 18.2 BYOD Security Requirements

**If accessing company email on personal device**:
- Device must have passcode/biometric
- Must install MDM profile (Mobile Device Management)
- Must enable device encryption
- Company can remotely wipe corporate data (only)
- Must report lost/stolen device immediately

**Employee privacy**:
- MDM only manages company data
- Personal data not accessible by company
- Remote wipe targets company partition only

---

## 19. Removable Media and Data Transfer

### 19.1 USB Drives and External Storage

**Company policy**:
- USB drives prohibited for restricted/confidential data
- If required: Use encrypted company-provided USB only
- Never use found USB drives (security risk)
- External hard drives: Encrypted, company-approved only

**Alternatives**:
- Cloud file sharing (Google Drive)
- Secure file transfer service
- Direct network transfer

### 19.2 Printing

**Confidential documents**:
- Retrieve immediately from printer
- Don't leave sensitive documents in printer tray
- Shred when no longer needed
- Follow-me printing (badge required) for restricted docs

---

## 20. Security Metrics and KPIs

### 20.1 Tracked Metrics

| Metric | Target | Frequency |
|--------|--------|-----------|
| Phishing click rate | <5% | Quarterly |
| Security training completion | 100% | Monthly |
| Unpatched critical vulnerabilities | 0 | Daily |
| Mean time to patch critical | <24 hours | Per incident |
| Access reviews completion | 100% | Quarterly |
| Failed login attempts (anomalies) | <10/month | Daily monitoring |
| Security incidents | 0 | Monthly |
| Mean time to detect | <4 hours | Per incident |
| Mean time to respond | <2 hours | Per incident |

### 20.2 Security Dashboard

Available to all employees at security.nexatech.jp:
- Current security posture
- Vulnerability status
- Training completion status
- Recent incidents (anonymized)
- Security tips

---

## 21. Policy Violations and Consequences

### 21.1 Violation Severity

**Minor violations** (First offense: Warning):
- Accessing company email on personal device without MDM
- Using public WiFi without VPN (no data accessed)
- Delayed reporting of lost device (<24 hours)
- Leaving computer unlocked in office

**Major violations** (Immediate termination):
- Intentional data breach or exfiltration
- Sharing customer data externally
- Disabling security controls
- Installing malware/unauthorized software
- Sharing credentials
- Repeated minor violations after warning

**Criminal violations** (Termination + legal action):
- Stealing customer data
- Selling company information
- Sabotage
- Insider trading based on company data

### 21.2 Reporting Violations

**To report policy violation**:
- security-violation@nexatech.jp
- Anonymous hotline: 0120-XXX-XXX
- Speak to manager or HR

**Whistleblower protection**: No retaliation for good-faith reporting.

---

## 22. Exception Requests

### 22.1 Policy Exceptions

Sometimes legitimate business need requires exception:
- Request via security-exception@nexatech.jp
- Provide business justification
- Describe risk mitigation
- Time-limited exceptions only

**Approval required**:
- Minor exceptions: Manager + CTO
- Major exceptions: CTO + CEO
- Customer data exceptions: CEO only

**Review**: All exceptions reviewed quarterly, most expire after 90 days.

---

## 23. Related Policies

- **POLICY-HR-001**: Remote Work Policy
- **POLICY-IT-002**: Acceptable Use Policy
- **POLICY-IT-003**: Data Privacy Policy
- **POLICY-IT-004**: Business Continuity Policy

---

## 24. Security Contacts

**Security Team**:
- General security questions: security@nexatech.jp
- Report incident: security-incident@nexatech.jp (24/7)
- Report phishing: security-phishing@nexatech.jp
- Policy exceptions: security-exception@nexatech.jp

**CTO (Yuki Nakamura)**: yuki.nakamura@nexatech.jp

---

## 25. Policy Change History

| Version | Date | Changes | Approved By |
|---------|------|---------|-------------|
| 1.0 | 2022-01-15 | Initial policy | CEO, CTO |
| 2.0 | 2023-06-01 | Added BYOD, enhanced incident response | CEO, CTO |
| 2.5 | 2024-05-01 | Added security metrics, training requirements | CTO |
| 3.0 | 2024-10-01 | Major update post-security incident: quarterly audits, enhanced monitoring, transparent incident response | CEO, CTO |

---

**Policy Acknowledgment**:
All employees must read and acknowledge this policy annually via HR system.

---

**END OF POLICY**