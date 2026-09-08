"""
App-category reference: for each generic EdTech app archetype, the scopes a
*reasonable* implementation would need, and the scopes that would be a real
outlier for that category.

These are deliberately generic archetypes ("Flashcard/Quiz Tool") rather than
real product names -- the goal is to teach the *pattern* of over-permissioning,
not to make claims about any specific real company's actual app.
"""

CATEGORIES = {
    "Flashcard / Quiz Tool": {
        "expected": ["openid", "userinfo.email", "userinfo.profile", "drive.file"],
        "plausible_extra": ["classroom.courses.readonly"],
        "outlier_examples": ["gmail.send", "contacts.readonly", "drive", "gmail.readonly"],
    },
    "Video Conferencing": {
        "expected": ["openid", "userinfo.email", "userinfo.profile", "calendar.readonly"],
        "plausible_extra": ["calendar.events"],
        "outlier_examples": ["gmail.modify", "contacts", "drive.readonly"],
    },
    "Digital Whiteboard": {
        "expected": ["openid", "userinfo.email", "userinfo.profile", "drive.file"],
        "plausible_extra": [],
        "outlier_examples": ["gmail.send", "drive", "admin.directory.user.readonly"],
    },
    "Gradebook / LMS Sync": {
        "expected": ["openid", "userinfo.email", "classroom.courses.readonly",
                     "classroom.rosters.readonly"],
        "plausible_extra": ["classroom.student-submissions.students.readonly"],
        "outlier_examples": ["gmail.send", "contacts", "drive"],
    },
    "Reading / Library App": {
        "expected": ["openid", "userinfo.email", "userinfo.profile"],
        "plausible_extra": ["drive.file"],
        "outlier_examples": ["contacts.readonly", "gmail.readonly", "drive"],
    },
    "Attendance Tracker": {
        "expected": ["openid", "userinfo.email", "classroom.rosters.readonly"],
        "plausible_extra": ["classroom.courses.readonly", "spreadsheets"],
        "outlier_examples": ["gmail.send", "contacts", "drive.readonly"],
    },
    "Parent Communication App": {
        "expected": ["openid", "userinfo.email", "userinfo.profile", "gmail.send"],
        "plausible_extra": ["contacts.readonly"],
        "outlier_examples": ["gmail.modify", "drive", "admin.directory.user.readonly"],
    },
    "STEM Simulation Tool": {
        "expected": ["openid", "userinfo.email", "userinfo.profile"],
        "plausible_extra": ["drive.file"],
        "outlier_examples": ["gmail.send", "contacts", "classroom.rosters.readonly"],
    },
    "Survey / Forms Tool": {
        "expected": ["openid", "userinfo.email", "forms.body"],
        "plausible_extra": ["drive.file", "spreadsheets"],
        "outlier_examples": ["gmail.readonly", "contacts", "drive"],
    },
    "Tutoring Platform": {
        "expected": ["openid", "userinfo.email", "userinfo.profile", "calendar.events"],
        "plausible_extra": ["classroom.courses.readonly"],
        "outlier_examples": ["gmail.modify", "contacts", "admin.directory.user.readonly"],
    },
    "Classroom Management Tool": {
        "expected": ["openid", "userinfo.email", "classroom.courses.readonly",
                     "classroom.rosters.readonly", "drive.file"],
        "plausible_extra": ["calendar.events", "spreadsheets"],
        "outlier_examples": ["gmail.send", "contacts", "admin.directory.user.readonly"],
    },
}
