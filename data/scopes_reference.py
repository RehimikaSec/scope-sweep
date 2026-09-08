"""
OAuth scope reference catalog.

Sensitivity tiers follow Google's own public classification of OAuth scopes
used in the OAuth API verification process:
  - "recommended": low-sensitivity, general-purpose scopes
  - "sensitive":    scopes granting access to private user data
  - "restricted":   scopes granting broad or highly private access
    (full Drive, full Gmail, admin directory, etc.)

This file hand-codes a representative subset of real Google Workspace scope
identifiers into that three-tier system, plus a short human-readable
description of what the scope actually grants. It is intentionally NOT an
exhaustive list -- it's enough real, correctly-classified scopes to build a
credible synthetic dataset without needing live access to any real tenant.

Tier weights are the numeric backbone every downstream feature is built on.
"""

TIER_WEIGHT = {
    "recommended": 1,
    "sensitive": 3,
    "restricted": 6,
}

SCOPES = {
    "openid": {
        "tier": "recommended",
        "label": "Confirm identity (OpenID)",
        "desc": "Confirms who is signing in. Grants no access to user content.",
    },
    "userinfo.email": {
        "tier": "recommended",
        "label": "See primary email address",
        "desc": "Reads the user's email address, nothing else.",
    },
    "userinfo.profile": {
        "tier": "recommended",
        "label": "See basic profile info",
        "desc": "Reads the user's name and profile photo.",
    },
    "drive.file": {
        "tier": "recommended",
        "label": "Access files created by this app",
        "desc": "Can only see or edit files the app itself created -- not the rest of Drive.",
    },
    "classroom.courses.readonly": {
        "tier": "sensitive",
        "label": "View Google Classroom course list",
        "desc": "Reads course names and metadata, not student work or rosters.",
    },
    "calendar.readonly": {
        "tier": "sensitive",
        "label": "View calendar",
        "desc": "Reads all events on the user's calendar, including titles and attendees.",
    },
    "calendar.events": {
        "tier": "sensitive",
        "label": "Manage calendar events",
        "desc": "Can create, edit, or delete events on the user's calendar.",
    },
    "contacts.readonly": {
        "tier": "sensitive",
        "label": "View contacts",
        "desc": "Reads the user's full contact list, including emails and phone numbers.",
    },
    "spreadsheets": {
        "tier": "sensitive",
        "label": "Read/write Google Sheets",
        "desc": "Can open, edit, or create any spreadsheet the user can access.",
    },
    "forms.body": {
        "tier": "sensitive",
        "label": "Read/write Google Forms",
        "desc": "Can view and edit the content and structure of Forms the user owns.",
    },
    "classroom.rosters.readonly": {
        "tier": "sensitive",
        "label": "View class rosters",
        "desc": "Reads which students are enrolled in a teacher's classes -- student PII.",
    },
    "drive.readonly": {
        "tier": "sensitive",
        "label": "View all Drive files",
        "desc": "Can read every file the user can see in Drive, not just app-created ones.",
    },
    "gmail.send": {
        "tier": "sensitive",
        "label": "Send email as the user",
        "desc": "Can send email from the user's account without further confirmation.",
    },
    "gmail.readonly": {
        "tier": "restricted",
        "label": "Read all email",
        "desc": "Can read the full content of every email in the user's mailbox.",
    },
    "gmail.modify": {
        "tier": "restricted",
        "label": "Read, send, and delete email",
        "desc": "Full read/write control of the mailbox except permanent deletion.",
    },
    "drive": {
        "tier": "restricted",
        "label": "Full access to Drive",
        "desc": "Can view, edit, move, or delete any file in the user's Drive.",
    },
    "contacts": {
        "tier": "restricted",
        "label": "Manage contacts",
        "desc": "Can read and modify the user's entire contact list.",
    },
    "classroom.student-submissions.students.readonly": {
        "tier": "restricted",
        "label": "View student coursework",
        "desc": "Reads submitted student assignments and grades -- highly sensitive student PII.",
    },
    "admin.directory.user.readonly": {
        "tier": "restricted",
        "label": "View all users in the organization",
        "desc": "Admin-level scope: reads every user account in the entire school domain.",
    },
}

# Scope combinations that are individually moderate but materially riskier
# together than the sum of their parts. Each entry: (frozenset(scope_ids), reason).
DANGEROUS_COMBOS = [
    (frozenset({"contacts.readonly", "gmail.send"}),
     "Can harvest the user's contact list and silently send email as them -- a "
     "textbook spam or phishing pipeline, even though each scope alone looks tame."),
    (frozenset({"classroom.rosters.readonly", "drive"}),
     "Can see which students are in a class AND move/export/share any file in "
     "Drive -- a plausible path to exfiltrating student records."),
    (frozenset({"calendar.readonly", "contacts.readonly", "userinfo.email"}),
     "Combined, these scopes build a fairly complete behavioral and social profile "
     "of the user, well beyond what any single scope suggests."),
    (frozenset({"gmail.readonly", "contacts.readonly"}),
     "Full mailbox read plus the contact list is enough to reconstruct a user's "
     "entire communication graph."),
    (frozenset({"admin.directory.user.readonly", "gmail.send"}),
     "Can enumerate every user in the school domain and send email as the "
     "requesting account -- a mass-impersonation risk."),
]
